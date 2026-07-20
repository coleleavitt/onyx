"use client";

import { useField } from "formik";
import EmojiPicker from "@/refresh-components/inputs/EmojiPicker";

export interface EmojiPickerFieldProps {
  name: string;
  ariaLabel?: string;
  size?: "md" | "lg";
  disabled?: boolean;
}

/**
 * Formik-bound wrapper around {@link EmojiPicker}. Stores the selected emoji
 * glyph as the field's string value (empty string when cleared), so existing
 * form submit handlers that read `values.emoji` keep working unchanged.
 */
export default function EmojiPickerField({
  name,
  ariaLabel,
  size,
  disabled,
}: EmojiPickerFieldProps) {
  const [field, , helpers] = useField<string>(name);

  return (
    <EmojiPicker
      value={field.value}
      onChange={(emoji) => {
        void helpers.setValue(emoji ?? "");
        void helpers.setTouched(true);
      }}
      ariaLabel={ariaLabel}
      size={size}
      disabled={disabled}
    />
  );
}
