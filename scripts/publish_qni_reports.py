"""Copy the validated QNI report suite into the Git-tracked reports area."""
from scripts.publish_vni_reports import publish


if __name__ == '__main__':
    print(publish('QNI', 'qni_diurnal_nos_v2', 'build_qni_report_suite.py', 'publish_qni_reports.py'))
