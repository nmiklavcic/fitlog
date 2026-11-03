// Weights are always stored in kilograms; these helpers convert for display and input.
export const KG_PER_LB = 0.45359237;
export const CM_PER_IN = 2.54;

export function kgToDisplay(kg, units) {
  if (kg === null || kg === undefined) return null;
  return units === "lb" ? kg / KG_PER_LB : kg;
}

// "135" in lb -> 61.235 kg, rounded to grams (the API accepts 3 decimals).
export function inputToKg(value, units) {
  const number = parseFloat(String(value).replace(",", "."));
  if (Number.isNaN(number)) return null;
  const kg = units === "lb" ? number * KG_PER_LB : number;
  return Math.round(kg * 1000) / 1000;
}

export function trimNumber(value, digits = 1) {
  if (value === null || value === undefined) return "";
  return Number(value.toFixed(digits)).toString();
}

export function formatWeight(kg, units, digits = 1) {
  if (kg === null || kg === undefined) return "-";
  return `${trimNumber(kgToDisplay(kg, units), digits)} ${units}`;
}

export function formatVolume(kg, units) {
  if (!kg) return `0 ${units}`;
  return `${Math.round(kgToDisplay(kg, units)).toLocaleString()} ${units}`;
}

// Body measurements follow the same preference: kg users see cm, lb users see inches.
export function lengthUnit(units) {
  return units === "lb" ? "in" : "cm";
}

export function cmToDisplay(cm, units) {
  if (cm === null || cm === undefined) return null;
  return units === "lb" ? cm / CM_PER_IN : cm;
}

export function inputToCm(value, units) {
  const number = parseFloat(String(value).replace(",", "."));
  if (Number.isNaN(number)) return null;
  return Math.round((units === "lb" ? number * CM_PER_IN : number) * 10) / 10;
}
