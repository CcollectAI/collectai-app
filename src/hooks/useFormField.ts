/**
 * useFormField — hook for managing a single form field with validation.
 *
 * Usage:
 *   const title = useFormField(validate.compose(
 *     validate.required("Title"),
 *     validate.maxLength("Title", 255),
 *   ));
 *
 *   <TextInput
 *     value={title.value}
 *     onChangeText={title.onChange}
 *     onBlur={title.onBlur}
 *   />
 *   {title.error && <Text style={{ color: 'red' }}>{title.error}</Text>}
 *
 *   // On submit:
 *   const valid = title.validate();
 */

import { useState, useCallback, useRef } from 'react';
import type { Validator } from '@/lib/validate';

export interface FormField {
  value: string;
  error: string | null;
  touched: boolean;
  onChange: (text: string) => void;
  onBlur: () => void;
  /** Run validation and return true if valid. */
  validate: () => boolean;
  /** Reset field to initial state. */
  reset: () => void;
  /** Set value programmatically (marks as touched). */
  setValue: (text: string) => void;
}

export function useFormField(
  validator?: Validator,
  initialValue: string = '',
): FormField {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const validatorRef = useRef(validator);
  validatorRef.current = validator;

  const runValidation = useCallback((v: string): string | null => {
    if (!validatorRef.current) return null;
    return validatorRef.current(v);
  }, []);

  const onChange = useCallback((text: string) => {
    setValue(text);
    // Clear error on change (validate again on blur)
    if (error) {
      const newError = runValidation(text);
      setError(newError);
    }
  }, [error, runValidation]);

  const onBlur = useCallback(() => {
    setTouched(true);
    setError(runValidation(value));
  }, [value, runValidation]);

  const validate = useCallback((): boolean => {
    setTouched(true);
    const err = runValidation(value);
    setError(err);
    return err === null;
  }, [value, runValidation]);

  const reset = useCallback(() => {
    setValue(initialValue);
    setError(null);
    setTouched(false);
  }, [initialValue]);

  const setValueManual = useCallback((text: string) => {
    setValue(text);
    setTouched(true);
    setError(runValidation(text));
  }, [runValidation]);

  return {
    value,
    error,
    touched,
    onChange,
    onBlur,
    validate,
    reset,
    setValue: setValueManual,
  };
}

/**
 * Validate all fields and return true if all are valid.
 * Usage: const allValid = validateAll(title, price, category);
 */
export function validateAll(...fields: FormField[]): boolean {
  return fields.every((f) => f.validate());
}
