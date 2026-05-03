export function redactAuthUiError(message: string): string {
  return message.replace(/\b(code|password|token|secret)=\S+/gi, '$1=[redacted]')
}
