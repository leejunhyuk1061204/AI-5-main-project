import * as SQLite from 'expo-sqlite';

const DB_NAME = 'offline.db';

export interface QueuedRequest {
    id?: number;
    url: string;
    method: string;
    headers?: string; // JSON string
    body?: string;    // JSON string
    timestamp: number;
    retryCount: number;
}

class OfflineStorage {
    private db: SQLite.SQLiteDatabase | null = null;

    constructor() {
        this.init();
    }

    private async init() {
        try {
            this.db = await SQLite.openDatabaseAsync(DB_NAME);
            await this.db.execAsync(`
                CREATE TABLE IF NOT EXISTS request_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL,
                    headers TEXT,
                    body TEXT,
                    timestamp INTEGER NOT NULL,
                    retryCount INTEGER DEFAULT 0
                );
            `);
            console.log('[OfflineStorage] Database initialized');
        } catch (e) {
            console.error('[OfflineStorage] Failed to init DB', e);
        }
    }

    private async ensureDb() {
        if (!this.db) {
            await this.init();
        }
        return this.db!;
    }

    async addToQueue(req: Omit<QueuedRequest, 'id' | 'retryCount'>) {
        try {
            const db = await this.ensureDb();
            await db.runAsync(
                'INSERT INTO request_queue (url, method, headers, body, timestamp, retryCount) VALUES (?, ?, ?, ?, ?, 0)',
                req.url, req.method, req.headers || '{}', req.body || '', req.timestamp
            );
            console.log('[OfflineStorage] Request queued:', req.url);
        } catch (e) {
            console.error('[OfflineStorage] Failed to queue request', e);
        }
    }

    async getQueue(): Promise<QueuedRequest[]> {
        try {
            const db = await this.ensureDb();
            const result = await db.getAllAsync<QueuedRequest>('SELECT * FROM request_queue ORDER BY timestamp ASC');
            return result;
        } catch (e) {
            console.error('[OfflineStorage] Failed to get queue', e);
            return [];
        }
    }

    async removeFromQueue(id: number) {
        try {
            const db = await this.ensureDb();
            await db.runAsync('DELETE FROM request_queue WHERE id = ?', id);
        } catch (e) {
            console.error('[OfflineStorage] Failed to remove item', id, e);
        }
    }

    async clearQueue() {
        try {
            const db = await this.ensureDb();
            await db.runAsync('DELETE FROM request_queue');
        } catch (e) {
            console.error('[OfflineStorage] Failed to clear queue', e);
        }
    }
}

export default new OfflineStorage();
