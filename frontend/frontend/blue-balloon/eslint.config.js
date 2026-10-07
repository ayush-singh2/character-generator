import js from '@eslint/js';
import globals from 'globals';
export default [js.configs.recommended, {files: ['src/**/*.{js,jsx}', 'tests/**/*.js'], languageOptions: {ecmaVersion: 'latest', sourceType: 'module', parserOptions: {ecmaFeatures: {jsx: true}}, globals: {...globals.browser, ...globals.node}}, rules: {'no-unused-vars': ['error', {varsIgnorePattern: '^[A-Z_]', args: 'none', caughtErrors: 'none'}]}}];
