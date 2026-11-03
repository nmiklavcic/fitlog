// The workout being logged lives in localStorage until "Finish", so a refresh or a
// closed tab mid-workout loses nothing. Weights are kept as the strings the user typed
// (in the units they had when they started) and converted to kg only when saving.
import { useEffect, useState } from "react";
import { todayIso } from "./format";

const EVENT = "liftlog:draft";
const key = (userId) => `liftlog:draft:${userId}`;

export function loadDraft(userId) {
  try {
    return JSON.parse(localStorage.getItem(key(userId)));
  } catch {
    return null;
  }
}

export function saveDraft(userId, draft) {
  try {
    localStorage.setItem(key(userId), JSON.stringify(draft));
  } catch {
    // Storage full or blocked (private mode): the draft just won't survive a reload.
  }
  window.dispatchEvent(new Event(EVENT));
}

export function clearDraft(userId) {
  try {
    localStorage.removeItem(key(userId));
  } catch {
    // ignore
  }
  window.dispatchEvent(new Event(EVENT));
}

export function newDraft({ units, date, title = "", templateId = null, exercises = [], workoutId = null }) {
  return {
    workoutId, // set when editing an existing workout
    templateId,
    title,
    performed_on: date || todayIso(),
    started_at: workoutId ? null : new Date().toISOString(),
    units,
    exercises,
  };
}

export function useHasDraft(userId) {
  const [has, setHas] = useState(() => Boolean(userId && loadDraft(userId)));
  useEffect(() => {
    const update = () => setHas(Boolean(userId && loadDraft(userId)));
    update();
    window.addEventListener(EVENT, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(EVENT, update);
      window.removeEventListener("storage", update);
    };
  }, [userId]);
  return has;
}
