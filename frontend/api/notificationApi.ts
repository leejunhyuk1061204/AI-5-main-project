import api from './axios';

export interface Notification {
    id: number;
    title: string;
    body: string;
    type: 'MAINTENANCE_ALERT' | 'COMMUNITY_ALERT' | 'SYSTEM_ALERT';
    isRead: boolean;
    createdAt: string;
}

export const getMyNotifications = async (): Promise<Notification[]> => {
    try {
        const response = await api.get('/api/v1/notifications');
        return response.data.data;
    } catch (error) {
        console.error('Failed to fetch notifications:', error);
        return [];
    }
};

export const markAsRead = async (id: number): Promise<void> => {
    try {
        await api.patch(`/api/v1/notifications/${id}/read`);
    } catch (error) {
        console.error(`Failed to mark notification ${id} as read:`, error);
    }
};
