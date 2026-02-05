import * as SQLite from 'expo-sqlite';

const DB_NAME = 'offline.db';
const MAX_QUEUE_SIZE = 50; // [11단계] 최대 50배치 (약 150분 분량)

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

            // [11단계] 용량 제한 및 FIFO 정책
            const countResult = await db.getFirstAsync<{ count: number }>('SELECT COUNT(*) as count FROM request_queue');
            const currentCount = countResult?.count ?? 0;

            if (currentCount >= MAX_QUEUE_SIZE) {
                // [11단계 피드백] 가장 오래된 데이터 1개 삭제 (FIFO)
                // timestamp가 동일할 경우를 대비해 id ASC 오더링 추가하여 정합성 보장
                const oldest = await db.getFirstAsync<QueuedRequest>('SELECT * FROM request_queue ORDER BY timestamp ASC, id ASC LIMIT 1');
                if (oldest && oldest.id) {
                    await db.runAsync('DELETE FROM request_queue WHERE id = ?', oldest.id);
                    console.warn(`[OfflineDrop] dropped=1 reason=capacity url=${oldest.url}`);
                }
            }

            await db.runAsync(
                'INSERT INTO request_queue (url, method, headers, body, timestamp, retryCount) VALUES (?, ?, ?, ?, ?, 0)',
                req.url, req.method, req.headers || '{}', req.body || '', req.timestamp
            );
            console.log('[OfflineStorage] Request queued:', req.url);
        } catch (e) {
            console.error('[OfflineStorage] Failed to queue request', e);
        }
    }

    async isUrlQueued(url: string): Promise<boolean> {
        try {
            const db = await this.ensureDb();
            const result = await db.getFirstAsync<{ count: number }>('SELECT COUNT(*) as count FROM request_queue WHERE url = ?', url);
            return (result?.count ?? 0) > 0;
        } catch (e) {
            console.error('[OfflineStorage] Failed to check url queue', e);
            return false;
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
