const data = JSON.parse(document.querySelector("#data").textContent);
const {observations, presets, features, directions, aggregations} = data;
const $ = selector => document.querySelector(selector);
const key = (configuration, period) => JSON.stringify([configuration, period]);
const timestamp = value => value?.slice(0, 16).replace("T", " ") ?? "";
const number = value => value == null ? "–" : value.toLocaleString("en-AU", {
  minimumFractionDigits: 1, maximumFractionDigits: 1
});
const directionLabel = {nsw_sa: "NSW → SA", sa_nsw: "SA → NSW"};
const targetLabel = {tight: "Tightest", mean: "Mean"};
const supportLabel = {multi_day: "Multi-day", single_day_example: "Single-day example", unsupported: "Unsupported"};
const presetLabel = {lower_residual: "Lower residual load", median_residual: "Median residual load", higher_residual: "Higher residual load"};
const periodLabel = {overnight: "Overnight", morning: "Morning", solar: "Solar hours", evening: "Evening"};
const probabilities = [0.1, 0.5, 0.9];
const roundingToleranceMw = 1e-8;
const inputColumns = ["time", "configuration", ...features];
const scoreColumns = ["time", "configuration", "delivery_period", "direction", "aggregation",
  "unit", "p10_mw", "p50_mw", "p90_mw", "intervals", "distinct_days", "dominant_setter",
  "dominant_setter_intervals", "support", "comparable_days", "support_reason"];
const supportColumns = ["time", "study_day", "configuration", "delivery_period", ...features, ...directions.flatMap(
  direction => [...aggregations, "setter", "minimum_time"].map(field => direction + "_" + field)
), ...data.episode_fields];

function groupRows(rows, valueOf) {
  const groups = new Map();
  for (const row of rows) {
    const value = valueOf(row);
    if (!groups.has(value)) groups.set(value, []);
    groups.get(value).push(row);
  }
  return groups;
}

function quantile(sorted, probability) {
  const rank = (sorted.length - 1) * probability;
  const low = Math.floor(rank);
  return sorted[low] + (rank - low) * (sorted[Math.ceil(rank)] - sorted[low]);
}

const ordered = values => [...values].sort((left, right) => left - right);
const byDay = groupRows(observations, row => row.study_day);
const seenConfigurations = new Set(observations.map(row => row.configuration));
const evidenced = observations.filter(row => row.configuration_evidenced);
const byConfiguration = groupRows(evidenced, row => row.configuration);
const cohorts = new Map();
for (const [cohortKey, rows] of groupRows(evidenced, row => key(row.configuration, row.delivery_period))) {
  const ranges = new Map();
  for (const feature of features) {
    const values = ordered(rows.map(row => row[feature]).filter(Number.isFinite));
    if (!values.length) continue;
    ranges.set(feature, {
      low: values[0],
      high: values[values.length - 1],
      scale: Math.max(data.floor, quantile(values, 0.75) - quantile(values, 0.25))
    });
  }
  cohorts.set(cohortKey, {rows, ranges});
}
const presetsByCohort = groupRows(presets, row => key(row.configuration, row.delivery_period));

function deliveryPeriod(time) {
  const minute = (Number(time.slice(11, 13)) * 60 + Number(time.slice(14, 16)) - 15 + 1440) % 1440;
  return data.periods.find(([, start, end]) => start <= minute && minute < end)?.[0] ?? "overnight";
}

function estimate(query) {
  const cohort = cohorts.get(key(query.configuration, query.period));
  let rows = [];
  let reason = "";
  if (!byConfiguration.has(query.configuration)) {
    reason = seenConfigurations.has(query.configuration)
      ? "The commissioning cap is unverified in the observed configuration."
      : "The configuration is absent from this study.";
  } else if (!cohort) {
    reason = "The configuration has no observation in this delivery period.";
  } else {
    const entered = features.filter(feature => Number.isFinite(query[feature]));
    const outside = entered.find(feature => {
      const range = cohort.ranges.get(feature);
      return !range || query[feature] < range.low - roundingToleranceMw
        || query[feature] > range.high + roundingToleranceMw;
    });
    if (outside) {
      reason = "The observed cohort does not cover " + outside.replace("_", " ") + " at the entered MW.";
    } else {
      rows = cohort.rows.filter(row => entered.every(feature => Number.isFinite(row[feature])
        && Math.abs(row[feature] - query[feature]) <= cohort.ranges.get(feature).scale + roundingToleranceMw));
      if (!rows.length) reason = "No interval meets all entered MW conditions together.";
    }
  }
  const days = [...new Set(rows.map(row => row.study_day))].sort();
  const support = days.length > 1 ? "multi_day" : days.length ? "single_day_example" : "unsupported";
  const estimates = directions.flatMap(direction => {
    const counts = new Map();
    for (const row of rows) {
      const setter = row[direction + "_setter"] ?? "unresolved";
      counts.set(setter, (counts.get(setter) ?? 0) + 1);
    }
    const dominant = [...counts.keys()].sort().sort((left, right) => counts.get(right) - counts.get(left))[0] ?? "";
    return aggregations.map(aggregation => {
      const values = ordered(rows.map(row => row[direction + "_" + aggregation]));
      const [p10, p50, p90] = values.length ? probabilities.map(item => quantile(values, item)) : [null, null, null];
      return {
        time: query.time ?? "", configuration: query.configuration, delivery_period: query.period,
        direction, aggregation, unit: "MW", p10_mw: p10, p50_mw: p50, p90_mw: p90,
        intervals: rows.length, distinct_days: days.length, dominant_setter: dominant,
        dominant_setter_intervals: counts.get(dominant) ?? 0, support, comparable_days: days.join("|"),
        support_reason: reason
      };
    });
  });
  return {query, rows, days, support, reason, estimates};
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function labeledCell(value, label, className) {
  const cell = element("td", value, className);
  cell.dataset.label = label;
  return cell;
}

function option(value, label) {
  return new Option(label, value);
}

function rowsTable(headers, rows) {
  const wrapper = element("div", null, "tablewrap");
  wrapper.tabIndex = 0;
  wrapper.setAttribute("aria-label", headers.join(", "));
  const table = element("table");
  const head = element("thead");
  const heading = element("tr");
  for (const header of headers) {
    const cell = element("th", header);
    cell.scope = "col";
    heading.append(cell);
  }
  const body = element("tbody");
  for (const row of rows) {
    const line = element("tr");
    for (const value of row) line.append(element("td", value));
    body.append(line);
  }
  head.append(heading);
  table.append(head, body);
  wrapper.append(table);
  return wrapper;
}

function bootstrapCounts(days) {
  let state = 713;
  const samples = [];
  for (let repeat = 0; repeat < data.replicates; repeat++) {
    const counts = Array(days).fill(0);
    for (let draw = 0; draw < days; draw++) {
      state ^= state << 13;
      state ^= state >>> 17;
      state ^= state << 5;
      counts[Math.floor((state >>> 0) / 2 ** 32 * days)]++;
    }
    samples.push(counts);
  }
  return samples;
}

function dayIntervals(result, target, dayCounts) {
  const dayIndex = new Map(result.days.map((day, index) => [day, index]));
  const rows = [...result.rows].sort((left, right) => left[target] - right[target]);
  const values = rows.map(row => row[target]);
  const days = rows.map(row => dayIndex.get(row.study_day));
  const draws = probabilities.map(() => []);
  for (const counts of dayCounts) {
    let total = 0;
    const cumulative = days.map(day => total += counts[day]);
    probabilities.forEach((probability, index) => {
      const rank = (total - 1) * probability;
      const low = Math.floor(rank);
      const left = values[cumulative.findIndex(value => value > low)];
      const right = values[cumulative.findIndex(value => value > Math.ceil(rank))];
      draws[index].push(left + (rank - low) * (right - left));
    });
  }
  return draws.map(values => {
    const sample = ordered(values);
    return [quantile(sample, 0.025), quantile(sample, 0.975)];
  });
}

function showDetail(result, scroll = true) {
  const detail = $("#detail");
  detail.replaceChildren(element("h3", result.query.time ? result.query.time + " NEM · supporting observations" : "Supporting observations"));
  const cohort = result.query.configuration + " · " + periodLabel[result.query.period];
  detail.append(element("p", cohort + ". " + supportLabel[result.support] + ". " + result.reason));
  if (result.rows.length) {
    detail.append(element("p", "Comparable NEM days · " + result.days.join(", "), "days"));
    if (result.days.length > 1) {
      const counts = bootstrapCounts(result.days.length);
      const intervals = result.estimates.map(row => {
        const bounds = dayIntervals(result, row.direction + "_" + row.aggregation, counts);
        return [directionLabel[row.direction], targetLabel[row.aggregation],
          ...bounds.map(([low, high]) => number(low) + " to " + number(high))];
      });
      detail.append(rowsTable(["Direction", "Target", "P10 95% CI (MW)", "Median 95% CI (MW)", "P90 95% CI (MW)"], intervals));
    } else {
      detail.append(element("p", "The matching intervals come from one day. Treat the values as a historical example."));
    }
    const download = element("button", "Download all matching intervals");
    download.type = "button";
    download.addEventListener("click", () => downloadCsv("pec_matching_intervals.csv", supportColumns,
      result.rows.map(row => ({...row, time: timestamp(row.time), ...Object.fromEntries(
        directions.map(direction => [direction + "_minimum_time", timestamp(row[direction + "_minimum_time"])])
      )}))));
    const shown = result.rows.slice(0, 12);
    const headings = ["Half-hour", ...directions.flatMap(direction => [
      directionLabel[direction] + " minimum time", directionLabel[direction] + " setter",
      ...(data.episode_fields.includes(direction + "_episode_id") ? [directionLabel[direction] + " episode"] : [])
    ])];
    detail.append(element("p", "Showing " + shown.length + " of " + result.rows.length + " matching half-hours.", "hint"), download,
      rowsTable(headings, shown.map(row => [timestamp(row.time), ...directions.flatMap(direction => [
        timestamp(row[direction + "_minimum_time"]), row[direction + "_setter"] ?? "Unresolved",
        ...(data.episode_fields.includes(direction + "_episode_id") ? [row[direction + "_episode_id"] ?? ""] : [])
      ])])));
  }
  detail.hidden = false;
  if (scroll) detail.scrollIntoView({block: "nearest"});
}

function csvCell(value) {
  const text = String(value ?? "");
  // A configuration or setter can originate in a user-supplied CSV.
  const safe = typeof value === "string" && /^[=+\-@\t\r]/.test(text) ? "'" + text : text;
  return /[",\r\n]/.test(safe) ? '"' + safe.replaceAll('"', '""') + '"' : safe;
}

function downloadCsv(name, columns, rows) {
  const content = [columns.join(","), ...rows.map(row => columns.map(column => csvCell(row[column])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], {type: "text/csv;charset=utf-8"}));
  const link = element("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function parseCsv(text) {
  const source = text.replace(/^\uFEFF/, "");
  const rows = [];
  let cells = [];
  let field = "";
  let quoted = false;
  let closed = false;
  for (let index = 0; index <= source.length; index++) {
    const character = source[index] ?? "\n";
    if (index === source.length && quoted) throw Error("The CSV has an unterminated quoted field.");
    if (quoted) {
      if (character !== '"') {
        field += character;
      } else if (source[index + 1] === '"') {
        field += '"';
        index++;
      } else {
        quoted = false;
        closed = true;
      }
      continue;
    }
    if (character === "," || character === "\n" || character === "\r") {
      cells.push(field.trim());
      field = "";
      closed = false;
      if (character !== ",") {
        if (character === "\r" && source[index + 1] === "\n") index++;
        if (cells.some(Boolean)) rows.push(cells);
        cells = [];
      }
    } else if (character === '"' && !field && !closed) {
      quoted = true;
    } else {
      if (closed || character === '"') throw Error("The CSV has an invalid quote.");
      field += character;
    }
  }
  return rows;
}

function inputPath(text) {
  const [header, ...rows] = parseCsv(text);
  if (!header || !rows.length) throw Error("Use a header row and at least one half-hour.");
  if (header.some(column => !inputColumns.includes(column)) || new Set(header).size !== header.length
      || !["time", "configuration"].every(column => header.includes(column))) {
    throw Error("Use unique template headers, including time and configuration.");
  }
  let previous = "";
  return rows.map((cells, index) => {
    const row = index + 2;
    if (cells.length !== header.length) throw Error("Check the field count on CSV row " + row + ".");
    const input = Object.fromEntries(header.map((column, position) => [column, cells[position]]));
    const time = input.time.replace("T", " ").replace(/^(\d{4}-\d\d-\d\d \d\d:\d\d):00$/, "$1");
    const iso = time.replace(" ", "T") + ":00Z";
    const parsed = new Date(iso);
    if (!/^\d{4}-\d\d-\d\d [0-2]\d:(00|30)$/.test(time) || !Number.isFinite(parsed.valueOf())
        || timestamp(parsed.toISOString()) !== time || time <= previous) {
      throw Error("Enter an ascending, unique NEM half-hour on CSV row " + row + ".");
    }
    previous = time;
    if (!input.configuration) throw Error("Enter a configuration on CSV row " + row + ".");
    const query = {time, configuration: input.configuration, period: deliveryPeriod(time)};
    for (const feature of features) {
      if (!input[feature]) continue;
      const value = Number(input[feature]);
      if (!Number.isFinite(value)) throw Error("Use MW values on CSV row " + row + ".");
      query[feature] = value;
    }
    return query;
  });
}

function historicalQueries(day) {
  return byDay.get(day).map(row => ({...row, time: timestamp(row.time), period: row.delivery_period}));
}

const state = {results: []};

function clearResults() {
  state.results = [];
  $("#result-table tbody").replaceChildren();
  $("#result-wrap").hidden = true;
  $("#detail").hidden = true;
  $("#export-results").disabled = true;
  $("#status").textContent = "";
}

function present(queries, mode) {
  clearResults();
  $("#error").hidden = true;
  const results = queries.map(estimate);
  state.results = results;
  const fragment = document.createDocumentFragment();
  for (const result of results) {
    for (const row of result.estimates) {
      const tr = element("tr");
      const input = element("td");
      const details = element("button", row.time || periodLabel[row.delivery_period]);
      details.type = "button";
      details.title = row.time || row.configuration;
      details.addEventListener("click", () => showDetail(result));
      input.append(details);
      tr.append(input, element("td", directionLabel[row.direction]), element("td", targetLabel[row.aggregation]),
        ...[["P10 MW", row.p10_mw], ["Median MW", row.p50_mw], ["P90 MW", row.p90_mw]]
          .map(([label, value]) => labeledCell(number(value), label, "numeric")),
        labeledCell(row.intervals, "Intervals", "numeric"), labeledCell(row.distinct_days, "Days", "numeric"),
        labeledCell(row.dominant_setter || "–", "Historical setter at minimum"), element("td", supportLabel[row.support],
          row.support === "multi_day" ? "" : "thin"));
      fragment.append(tr);
    }
  }
  $("#result-table tbody").append(fragment);
  const counts = label => results.filter(result => result.support === label).length;
  const inputCount = results.length + (results.length === 1 ? " input" : " inputs");
  $("#status").textContent = mode + " · " + inputCount + " · " + counts("multi_day")
    + " multi-day · " + counts("single_day_example") + " single-day examples · " + counts("unsupported") + " unsupported";
  $("#result-wrap").hidden = false;
  $("#result-wrap").dataset.single = String(results.length === 1);
  $("#export-results").disabled = false;
  if (results.length === 1) showDetail(results[0], false);
}

const configure = $("#configuration");
const period = $("#period");
const preset = $("#preset");
const historical = $("#historical-day");
const configurations = [...byConfiguration.keys()].sort();
const largestConfiguration = configurations.slice().sort((a, b) => byConfiguration.get(b).length - byConfiguration.get(a).length)[0];
const allDays = [...byDay.keys()].sort();
const evidencedDays = allDays.filter(day => byDay.get(day).some(row => row.configuration_evidenced));
const latestWholeDay = evidencedDays.filter(day => {
  const rows = byDay.get(day);
  return rows.length === 48 && rows.every(row => row.configuration_evidenced);
}).at(-1) ?? evidencedDays.at(-1) ?? allDays.at(-1);
configure.replaceChildren(...configurations.map(name => option(name, name)));
configure.value = largestConfiguration ?? "";
period.replaceChildren(...Object.entries(periodLabel).map(([name, label]) => option(name, label)));
historical.replaceChildren(...allDays.map(day => option(day, day + " · " + byDay.get(day).length + " intervals")));
historical.value = latestWholeDay ?? "";

const fieldNodes = new Map();
for (const [region, regionFeatures] of groupRows(features, name => name.split("_")[0])) {
  const fields = element("fieldset");
  fields.append(element("legend", region));
  for (const feature of regionFeatures) {
    const metric = feature.split("_")[1];
    const field = element("input");
    field.type = "number";
    field.step = "any";
    field.name = feature;
    field.id = feature;
    field.setAttribute("aria-label", region.toUpperCase() + " " + metric + " MW");
    field.addEventListener("input", () => {
      preset.value = "custom";
      $("#preset-note").textContent = "Editable regional inputs.";
    });
    const label = element("label", metric[0].toUpperCase() + metric.slice(1) + " MW");
    label.append(field);
    fields.append(label);
    fieldNodes.set(feature, field);
  }
  $("#features").append(fields);
}

function setPreset() {
  const row = (presetsByCohort.get(key(configure.value, period.value)) ?? [])
    .find(item => item.preset === preset.value);
  if (preset.value !== "custom") {
    for (const [feature, input] of fieldNodes) input.value = row?.[feature] ?? "";
  } else {
    $("#feature-details").open = true;
  }
  $("#preset-note").textContent = row ? "Observed conditions at " + timestamp(row.time) + " NEM."
    : preset.value === "custom" ? "Editable regional inputs." : "Uses all intervals in the selected configuration and period.";
}

function updatePresets() {
  const rows = presetsByCohort.get(key(configure.value, period.value)) ?? [];
  preset.replaceChildren(option("reference", "Configuration reference"),
    ...rows.map(row => option(row.preset, presetLabel[row.preset])), option("custom", "Editable conditions"));
  preset.value = "reference";
  setPreset();
}

function updateConfiguration() {
  const rows = byConfiguration.get(configure.value) ?? [];
  const periods = [...groupRows(rows, row => row.delivery_period).entries()].sort((a, b) => b[1].length - a[1].length);
  period.value = periods[0]?.[0] ?? "overnight";
  updatePresets();
}

function conditionQuery() {
  const query = {configuration: configure.value, period: period.value};
  for (const [feature, field] of fieldNodes) if (field.value !== "") query[feature] = field.valueAsNumber;
  return query;
}

for (const tab of document.querySelectorAll("[data-mode]")) {
  tab.addEventListener("click", () => {
    for (const item of document.querySelectorAll("[data-mode]")) {
      const active = item === tab;
      item.setAttribute("aria-pressed", String(active));
      $("#" + item.dataset.mode + "-form").hidden = !active;
    }
    clearResults();
    $("#error").hidden = true;
  });
}
configure.addEventListener("change", updateConfiguration);
period.addEventListener("change", updatePresets);
preset.addEventListener("change", setPreset);
$("#conditions-form").addEventListener("submit", event => {
  event.preventDefault();
  present([conditionQuery()], "Regional conditions");
});
$("#upload-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    present(inputPath(await $("#path-file").files[0].text()), "Uploaded path");
  } catch (error) {
    clearResults();
    $("#error").textContent = error.message;
    $("#error").hidden = false;
  }
});
$("#historical-form").addEventListener("submit", event => {
  event.preventDefault();
  present(historicalQueries(historical.value), "Historical day");
});
$("#template").addEventListener("click", () => downloadCsv("pec_path_template.csv", inputColumns, historicalQueries(latestWholeDay)));
$("#export-day").addEventListener("click", () => downloadCsv("pec_input_" + historical.value + ".csv", inputColumns, historicalQueries(historical.value)));
$("#export-results").addEventListener("click", () => downloadCsv("pec_scenario_results.csv", scoreColumns,
  state.results.flatMap(result => result.estimates)));
updateConfiguration();
if (configurations.length) {
  $("#source").textContent += " · " + data.start + " to " + data.end;
  present([conditionQuery()], "Regional conditions");
} else {
  for (const control of document.querySelectorAll("main form button")) control.disabled = true;
  $("#status").textContent = "No evidenced configuration is available in the scenario data.";
}
