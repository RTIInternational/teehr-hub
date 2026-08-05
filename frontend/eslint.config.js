import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import importPlugin from 'eslint-plugin-import';
import globals from 'globals';
import eslintPluginPrettierRecommended from 'eslint-plugin-prettier/recommended';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';

const sharedPlugins = {
  react,
  'react-hooks': reactHooks,
  'react-refresh': reactRefresh,
  'jsx-a11y': jsxA11y,
  import: importPlugin,
};

const sharedLanguageOptions = {
  ecmaVersion: 2020,
  globals: {
    ...globals.browser,
    ...globals.jest,
  },
  parserOptions: {
    ecmaVersion: 'latest',
    ecmaFeatures: { jsx: true },
    sourceType: 'module',
  },
};

const sharedRules = {
  ...js.configs.recommended.rules,
  ...react.configs.recommended.rules,
  ...react.configs['jsx-runtime'].rules,
  ...reactHooks.configs.recommended.rules,
  ...importPlugin.configs.recommended.rules,
  'react/jsx-no-target-blank': 'off',
  'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

  // Import rules
  'import/order': [
    'warn',
    {
      groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
      'newlines-between': 'never',
      alphabetize: { order: 'asc', caseInsensitive: true },
    },
  ],
  'import/no-unused-modules': 'off',
  'import/no-duplicates': 'error',

  // General code quality
  'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
  'no-console': ['warn', { allow: ['warn', 'error'] }],
  'prefer-const': 'warn',
  'no-var': 'error',

  // React specific
  'react/prop-types': 'off',
  'react/display-name': 'off',
  'react/no-unescaped-entities': 'warn',
  'react/jsx-key': 'error',

  // Accessibility
  'jsx-a11y/alt-text': 'warn',
  'jsx-a11y/aria-role': 'warn',
  'jsx-a11y/aria-props': 'warn',
  'jsx-a11y/aria-proptypes': 'warn',
  'jsx-a11y/role-supports-aria-props': 'warn',
  'jsx-a11y/aria-unsupported-elements': 'warn',
};

export default [
  {
    ignores: ['dist', 'build', 'node_modules', '*.config.js'],
  },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: sharedLanguageOptions,
    settings: {
      react: { version: 'detect' },
      'import/resolver': {
        node: {
          extensions: ['.ts', '.tsx', '.js', '.jsx'],
        },
      },
    },
    plugins: sharedPlugins,
    rules: sharedRules,
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ...sharedLanguageOptions,
      parser: tsParser,
    },
    plugins: {
      ...sharedPlugins,
      '@typescript-eslint': tsPlugin,
    },
    settings: {
      react: { version: 'detect' },
      'import/resolver': {
        typescript: true,
        node: {
          extensions: ['.ts', '.tsx', '.js', '.jsx'],
        },
      },
    },
    rules: {
      ...sharedRules,
      ...tsPlugin.configs.recommended.rules,
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
  {
    files: ['vite.config.ts'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
  eslintPluginPrettierRecommended,
];
