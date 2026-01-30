/**
 * Simple logger with debug mode support
 */
export class Logger {
  constructor(private debug: boolean) {}
  
  info(message: string, data?: Record<string, unknown>): void {
    const formatted = this.format("INFO", message, data);
    console.log(formatted);
  }
  
  warn(message: string, data?: Record<string, unknown>): void {
    const formatted = this.format("WARN", message, data);
    console.warn(formatted);
  }
  
  error(message: string, data?: Record<string, unknown>): void {
    const formatted = this.format("ERROR", message, data);
    console.error(formatted);
  }
  
  debugLog(message: string, data?: Record<string, unknown>): void {
    if (!this.debug) return;
    const formatted = this.format("DEBUG", message, data);
    console.log(formatted);
  }
  
  private format(level: string, message: string, data?: Record<string, unknown>): string {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [context-curator] [${level}]`;
    
    if (data) {
      return `${prefix} ${message} ${JSON.stringify(data)}`;
    }
    return `${prefix} ${message}`;
  }
}
