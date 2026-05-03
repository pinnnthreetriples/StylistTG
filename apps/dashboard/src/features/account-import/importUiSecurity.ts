export function redactImportUiError(message: string): string {
  return message.replace(/\b(api_hash|auth_key|session|password|token|secret)=\S+/gi, '$1=[redacted]')
}
