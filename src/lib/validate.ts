/**
 * Form validation utilities.
 *
 * Each validator returns an error message string or null if valid.
 *
 * Usage:
 *   const error = validate.required("Title")(value);
 *   // -> "Title is required" or null
 */

export type Validator = (value: string) => string | null;

/** Compose multiple validators — returns the first error, or null. */
export function compose(...validators: Validator[]): Validator {
  return (value: string) => {
    for (const v of validators) {
      const error = v(value);
      if (error) return error;
    }
    return null;
  };
}

/** Value must be non-empty after trimming. */
export function required(fieldName: string): Validator {
  return (value) =>
    value.trim().length === 0 ? `${fieldName} is required` : null;
}

/** Value must be at least `min` characters. */
export function minLength(fieldName: string, min: number): Validator {
  return (value) =>
    value.trim().length < min
      ? `${fieldName} must be at least ${min} characters`
      : null;
}

/** Value must be at most `max` characters. */
export function maxLength(fieldName: string, max: number): Validator {
  return (value) =>
    value.trim().length > max
      ? `${fieldName} must be at most ${max} characters`
      : null;
}

/** Value must be a valid number. */
export function numeric(fieldName: string): Validator {
  return (value) => {
    if (value.trim().length === 0) return null; // let `required` catch empty
    return isNaN(Number(value)) ? `${fieldName} must be a number` : null;
  };
}

/** Value must be a positive number (> 0). */
export function positiveNumber(fieldName: string): Validator {
  return (value) => {
    if (value.trim().length === 0) return null;
    const n = Number(value);
    if (isNaN(n)) return `${fieldName} must be a number`;
    return n <= 0 ? `${fieldName} must be greater than 0` : null;
  };
}

/** Value must be a valid email address. */
export function email(fieldName: string = "Email"): Validator {
  return (value) => {
    if (value.trim().length === 0) return null;
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(value.trim()) ? null : `${fieldName} must be a valid email`;
  };
}

/** Value must be a valid URL (http/https). */
export function url(fieldName: string = "URL"): Validator {
  return (value) => {
    if (value.trim().length === 0) return null;
    try {
      const u = new URL(value.trim());
      return u.protocol === "http:" || u.protocol === "https:"
        ? null
        : `${fieldName} must start with http:// or https://`;
    } catch {
      return `${fieldName} must be a valid URL`;
    }
  };
}

/** Value must match a date pattern YYYY-MM-DD. */
export function dateYMD(fieldName: string = "Date"): Validator {
  return (value) => {
    if (value.trim().length === 0) return null;
    const re = /^\d{4}-\d{2}-\d{2}$/;
    if (!re.test(value.trim())) return `${fieldName} must be YYYY-MM-DD`;
    const d = new Date(value.trim());
    return isNaN(d.getTime()) ? `${fieldName} is not a valid date` : null;
  };
}
