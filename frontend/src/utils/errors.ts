/**
 * Error classifier — maps raw backend/fetch errors to user-friendly
 * Ukrainian messages.  Never expose Python tracebacks or raw HTTP details.
 *
 * ## Usage
 *
 *    import { friendlyError } from '../utils/errors'
 *    setError(friendlyError(rawMessage))
 *
 * `friendlyError` returns a string suitable for display in `.error-msg`.
 * Pass an optional context object to help the classifier pick the best message.
 */

interface ErrorContext {
  /** What was the user trying to do? */
  action?: string
  /** Provider name (for API key errors) */
  provider?: string
  /** The raw HTTP status if known */
  status?: number
}

const NETWORK_PATTERNS = [
  /failed to fetch/i,
  /networkerror/i,
  /ERR_CONNECTION_REFUSED/i,
  /ERR_INTERNET_DISCONNECTED/i,
  /fetch failed/i,
  /Network Error/i,
  /connection refused/i,
]

const AUTH_PATTERNS = [
  /401/i,
  /403/i,
  /unauthorized/i,
  /forbidden/i,
  /invalid api key/i,
  /incorrect api key/i,
  /authentication failed/i,
  /not authenticated/i,
  /permission denied/i,
]

const RATE_LIMIT_PATTERNS = [
  /429/i,
  /rate limit/i,
  /too many requests/i,
  /quota exceeded/i,
  /resource.*exhausted/i,
]

const SERVER_ERROR_PATTERNS = [
  /500/i,
  /502/i,
  /503/i,
  /504/i,
  /internal server error/i,
  /bad gateway/i,
  /service unavailable/i,
  /gateway timeout/i,
]

const NOT_FOUND_PATTERNS = [
  /404/i,
  /not found/i,
]

const VALIDATION_PATTERNS = [
  /422/i,
  /validation error/i,
  /unprocessable/i,
]

/**
 * Strip Python traceback noise from a raw error string.
 * Keeps only the last meaningful line (the actual error message).
 */
function stripTraceback(raw: string): string {
  // Python traceback ends with "ExceptionType: message"
  const lines = raw.split('\n')
  // Walk backwards to find the last non-empty, non-traceback line
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim()
    if (!line) continue
    // Skip File "...", line N, in <module> style lines
    if (/^\s*File\s+".+",\s+line\s+\d+/.test(line)) continue
    // Skip "^" or "~~~" underline markers
    if (/^[\^~]+$/.test(line)) continue
    // Skip "Traceback (most recent call last):"
    if (/traceback/i.test(line)) continue
    return line
  }
  return raw
}

/**
 * Classify a raw error string into a user-friendly Ukrainian message.
 */
export function friendlyError(raw: string, ctx?: ErrorContext): string {
  const cleaned = stripTraceback(raw)

  // --- Cancellation (handled explicitly in UI, but safety net) ---
  if (/cancel/i.test(cleaned) && !/cancelled/i.test(ctx?.action ?? '')) {
    return 'Переклад скасовано.'
  }

  // --- Network ---
  for (const p of NETWORK_PATTERNS) {
    if (p.test(cleaned)) {
      return 'Не вдалося з\'єднатися з сервером MovaMC. Переконайтеся, що бекенд запущено (mova web).'
    }
  }

  // --- Timeout ---
  if (/timeout/i.test(cleaned) || /timed out/i.test(cleaned)) {
    return 'Сервер не відповідає вчасно. Спробуйте ще раз або зменшіть кількість модів.'
  }

  // --- Auth ---
  for (const p of AUTH_PATTERNS) {
    if (p.test(cleaned)) {
      const provider = ctx?.provider ? ` (${ctx.provider})` : ''
      return `Помилка автентифікації${provider}. Перевірте API-ключ у налаштуваннях провайдера.`
    }
  }

  // --- Rate limit ---
  for (const p of RATE_LIMIT_PATTERNS) {
    if (p.test(cleaned)) {
      return 'Перевищено ліміт запитів до API. Зачекайте хвилину і спробуйте знову.'
    }
  }

  // --- Server errors ---
  for (const p of SERVER_ERROR_PATTERNS) {
    if (p.test(cleaned)) {
      return 'Помилка на стороні API-провайдера. Спробуйте ще раз за кілька хвилин.'
    }
  }

  // --- Not found ---
  for (const p of NOT_FOUND_PATTERNS) {
    if (p.test(cleaned)) {
      return 'Не знайдено. Перевірте шлях до тек або вихідну мову.'
    }
  }

  // --- Validation ---
  for (const p of VALIDATION_PATTERNS) {
    if (p.test(cleaned)) {
      return `Неправильні дані: ${cleaned}. Перевірте налаштування і спробуйте знову.`
    }
  }

  // --- Generic — show cleaned message, no tracebacks ---
  // If the cleaned message is still ugly (very long, has file paths), sanitize
  if (cleaned.length > 200 || /[A-Z]:[\\/]/.test(cleaned) || /site-packages/.test(cleaned)) {
    return 'Сталася неочікувана помилка. Перезапустіть MovaMC і спробуйте знову.'
  }

  return cleaned || 'Сталася невідома помилка.'
}
