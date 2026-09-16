"""Small, explicit model grids and fold-local feature transformations."""
import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy.optimize import minimize
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler,SplineTransformer
from sklearn.linear_model import Ridge,ElasticNet,LogisticRegression
from sklearn.metrics import log_loss


class Transform:
    def fit(self,x):
        self.names=list(x.columns);self.lo=x.quantile(.001);self.hi=x.quantile(.999)
        self.imputer=SimpleImputer(add_indicator=True,keep_empty_features=True)
        z=self.imputer.fit_transform(x.clip(self.lo,self.hi,axis=1))
        self.scaler=StandardScaler().fit(z)
        return self
    def apply(self,x):
        if list(x.columns)!=self.names:raise ValueError('Feature schema changed')
        return self.scaler.transform(self.imputer.transform(x.clip(self.lo,self.hi,axis=1))).astype('float32')


class Candidate:
    def __init__(self,family,settings,classification=False):self.family=family;self.settings=settings;self.classification=classification
    def expand(self,z,fit=False):
        if self.family=='additive':
            if fit:self.spline=SplineTransformer(n_knots=self.settings['knots'],degree=2,include_bias=False,extrapolation='linear').fit(z[:,self.smooth])
            return np.column_stack([z,self.spline.transform(z[:,self.smooth])])
        if self.family=='regime':
            gates=[(z[:,i]<0).astype(float) for i in self.gates]
            return np.column_stack([z]+[z[:,self.smooth]*g[:,None] for g in gates])
        return z
    def fit(self,x,y,prepared=None,sample_weight=None):
        if prepared is None:self.transform=Transform().fit(x);z=self.transform.apply(x)
        else:self.transform,z=prepared
        names=list(x.columns)
        self.smooth=[i for i,n in enumerate(names) if n in ['upper_room','lower_room','upper_gen_tightening','lower_gen_tightening','hour_sin','hour_cos'] or n.endswith('__residual_demand')]
        if not self.smooth:self.smooth=list(range(min(4,len(names))))
        self.gates=[names.index(n) for n in ['upper_room','lower_room'] if n in names] or [0]
        z=self.expand(z,True)
        self.scale=1. if self.classification else max(float(np.std(y)),1.)
        settings=self.settings
        if self.family.startswith('boost'):
            params=dict(n_estimators=150,num_leaves=settings['leaves'],learning_rate=.04,min_child_samples=150,reg_lambda=10,n_jobs=2,verbosity=-1,random_state=741,deterministic=True,force_col_wise=True)
            self.model=lgb.LGBMClassifier(**params) if self.classification else lgb.LGBMRegressor(objective=settings.get('objective','regression_l1'),**params)
        elif self.classification:self.model=LogisticRegression(C=settings.get('C',.1),max_iter=1500)
        elif self.family=='elastic':self.model=ElasticNet(alpha=settings['alpha'],l1_ratio=settings['mix'],max_iter=2000,tol=.001)
        else:self.model=Ridge(alpha=settings.get('alpha',100))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            if sample_weight is None:self.model.fit(z,y/self.scale)
            else:self.model.fit(z,y/self.scale,sample_weight=sample_weight)
        self.warnings=[str(x.message) for x in caught]
        self.columns=len(names);self.expanded_columns=z.shape[1]
        return self
    def predict(self,x):
        return self.predict_prepared(self.transform.apply(x))
    def predict_prepared(self,z):
        z=self.expand(z)
        if self.family.startswith('boost'):return self.model.booster_.predict(z,num_threads=2)*self.scale
        return self.model.predict_proba(z)[:,1] if self.classification else self.model.predict(z)*self.scale


def grid(family,c,classification=False):
    m=c['models']
    if family.startswith('boost'):return [{'leaves':v,'objective':'regression' if family=='boost_l2' else 'regression_l1'} for v in m['boost_leaves']]
    if family=='elastic':return [{'alpha':a,'mix':b} for a in m['elastic_alpha'] for b in m['elastic_mix']]
    if family=='additive':return [{'knots':k,'alpha':a,'C':1/a} for k in m['spline_knots'] for a in m['spline_alpha']]
    if classification:return [{'C':v} for v in m['logistic_c']]
    return [{'alpha':a} for a in m['ridge']]


def select(family,x,y,xv,yv,c,classification=False):
    records=[];best=None;transform=Transform().fit(x)
    z=transform.apply(x);zv=transform.apply(xv)
    for params in grid(family,c,classification):
        model=Candidate(family,params,classification).fit(x,y,prepared=(transform,z))
        prediction=model.predict_prepared(zv)
        score=float(log_loss(yv,np.clip(prediction,1e-6,1-1e-6),labels=[0,1])) if classification else float(np.abs(yv-prediction).mean())
        records.append({'parameters':params,'validation_loss':score,'warnings':model.warnings})
        if best is None or score<best[0]:best=(score,model)
    return best[1],records


def forecast_pressure(d,fold,lead):
    """Expanding monthly out-of-fold aggregate pressure predictions; no in-sample stage-two features."""
    f=d['f'];idx=f.index
    target=np.column_stack([(f[s+'_gen_tightening']-f[s+'_gen_relief']).shift(-lead) for s in ['upper','lower']])
    x=d['base'][[c for c in d['base'] if c in ['upper_gen_tightening','upper_gen_relief','lower_gen_tightening','lower_gen_relief','flow_lag1','flow_delta']]]
    prediction=np.full((len(idx),2),np.nan)
    train_end=pd.Timestamp(fold.train_end)
    for month in pd.date_range('2024-09-01',train_end,freq='MS'):
        cutoff=min(month,train_end)
        tr=(idx>=pd.Timestamp(fold.train_start))&(idx+pd.Timedelta(minutes=lead*30)<cutoff)&np.isfinite(target).all(axis=1)
        end=min(month+pd.DateOffset(months=1),train_end)
        ev=(idx>=month)&(idx<end)
        if tr.sum()<500 or not ev.any():continue
        transformer=Transform().fit(x.loc[tr]);model=Ridge(alpha=100).fit(transformer.apply(x.loc[tr]),target[tr])
        prediction[ev]=model.predict(transformer.apply(x.loc[ev]))
    tr=(idx>=pd.Timestamp(fold.train_start))&(idx+pd.Timedelta(minutes=lead*30)<train_end)&np.isfinite(target).all(axis=1)
    ev=idx>=train_end
    if tr.sum()>=500:
        transformer=Transform().fit(x.loc[tr]);model=Ridge(alpha=100).fit(transformer.apply(x.loc[tr]),target[tr])
        prediction[ev]=model.predict(transformer.apply(x.loc[ev]))
    # Warm-up has an explicitly missing forecast, imputed only inside downstream fitting.
    return prediction


class LinearQuantiles:
    """Regularised linear quantiles using a smooth pinball approximation (epsilon .01 scaled MW)."""
    def fit(self,x,y,levels):
        self.transform=Transform().fit(x);z=self.transform.apply(x)
        self.scale=max(float(np.std(y)),1.);self.center=float(np.median(y))
        a=np.column_stack([np.ones(len(z)),z]);b=(y-self.center)/self.scale;self.levels=np.asarray(levels)
        shape=(a.shape[1],len(levels));initial=np.zeros(shape);initial[0]=np.quantile(b,levels)
        def objective(w):
            weights=w.reshape(shape);e=b[:,None]-a@weights;s=np.sqrt(e*e+.0001)
            loss=np.mean((self.levels-.5)*e+.5*s)+.01*np.sum(weights[1:]**2)
            der=-(self.levels-.5+.5*e/s)/(len(a)*len(levels))
            grad=a.T@der;grad[1:]+=.02*weights[1:]
            return loss,grad.ravel()
        result=minimize(objective,initial.ravel(),jac=True,method='L-BFGS-B',options={'maxiter':150,'ftol':1e-7})
        self.weights=result.x.reshape(shape);self.converged=bool(result.success)
        return self
    def predict(self,x):
        z=self.transform.apply(x);p=np.column_stack([np.ones(len(z)),z])@self.weights*self.scale+self.center
        return np.sort(p,axis=1)
