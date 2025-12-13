import React from 'react';
import { TextInput, TextInputProps } from 'react-native';

type SafeTextInputProps = TextInputProps & {
  label?: string;
};

export const SafeTextInput: React.FC<SafeTextInputProps> = ({ label, ...rest }) => {
  return (
    <TextInput
      {...rest}
      placeholderTextColor={rest.placeholderTextColor ?? '#999999'}
      autoCorrect={rest.autoCorrect ?? false}
    />
  );
};

export default SafeTextInput;
