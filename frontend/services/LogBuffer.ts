const MAX_LINES = 100000;

const lines: string[] = [];

function formatArgs(args: unknown[]): string {
    return args
        .map((a) => {
            if (a === null) return 'null';
            if (a === undefined) return 'undefined';
            if (typeof a === 'object') try { return JSON.stringify(a); } catch { return String(a); }
            return String(a);
        })
        .join(' ');
}

function timestamp(): string {
    return new Date().toISOString();
}

export const LogBuffer = {
    append(level: 'log' | 'warn' | 'error', ...args: unknown[]): void {
        try {
            const line = `${timestamp()} [${level.toUpperCase()}] ${formatArgs(args)}`;
            lines.push(line);
            if (lines.length > MAX_LINES) lines.splice(0, lines.length - MAX_LINES);
        } catch (_) {}
    },

    getContent(): string {
        return lines.join('\n') || '(no logs)';
    },

    clear(): void {
        lines.length = 0;
    },

    get lineCount(): number {
        return lines.length;
    },
};
