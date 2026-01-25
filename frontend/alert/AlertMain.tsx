import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, RefreshControl, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { getMyNotifications, markAsRead, Notification } from '../api/notificationApi';

export default function AlertMain() {
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [refreshing, setRefreshing] = useState(false);

    const loadNotifications = async () => {
        setRefreshing(true);
        const data = await getMyNotifications();
        setNotifications(data);
        setRefreshing(false);
    };

    useFocusEffect(
        useCallback(() => {
            loadNotifications();
        }, [])
    );

    const handleRead = async (id: number) => {
        // Optimistic update
        setNotifications(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n));
        await markAsRead(id);
    };

    const handleMarkAllAsRead = async () => {
        const unreadIds = notifications.filter(n => !n.isRead).map(n => n.id);
        if (unreadIds.length === 0) return;

        // Optimistic update
        setNotifications(prev => prev.map(n => ({ ...n, isRead: true })));

        // In a real app, we might want a 'markAllRead' API, but here we loop (simple version)
        // Or implement a batch API if available. For now loop is safe for small numbers.
        for (const id of unreadIds) {
            await markAsRead(id);
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diff = (now.getTime() - date.getTime()) / 1000; // seconds

        if (diff < 60) return '방금 전';
        if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
        return `${Math.floor(diff / 86400)}일 전`;
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            <View className="absolute inset-0 z-0">
                <View className="absolute inset-0 bg-[#0c0e12]" />
                <View className="absolute inset-0 bg-[#0c0e12]" />
            </View>

            <View className="flex-1 z-10">
                {/* Header */}
                <View className="px-6 py-5 flex-row items-center justify-between border-b border-white/5 bg-[#0c0e12]/80 backdrop-blur-md">
                    <Text className="text-white text-2xl font-bold tracking-tight">알림 센터</Text>
                    <TouchableOpacity
                        onPress={handleMarkAllAsRead}
                        className="flex-row items-center justify-center rounded-full px-3 py-1.5 active:bg-primary/10"
                    >
                        <MaterialIcons name="done-all" size={18} color="#0d7ff2" style={{ marginRight: 4 }} />
                        <Text className="text-xs font-bold text-primary">모두 읽음</Text>
                    </TouchableOpacity>
                </View>

                {/* Notification List */}
                <ScrollView
                    className="flex-1 p-5"
                    contentContainerStyle={{ paddingBottom: 100, gap: 16 }}
                    showsVerticalScrollIndicator={false}
                    refreshControl={
                        <RefreshControl refreshing={refreshing} onRefresh={loadNotifications} tintColor="#0d7ff2" />
                    }
                >
                    {notifications.length === 0 ? (
                        <View className="items-center justify-center py-20">
                            <MaterialIcons name="notifications-none" size={64} color="#334155" />
                            <Text className="text-slate-500 mt-4 text-center">
                                새로운 알림이 없습니다.
                            </Text>
                        </View>
                    ) : (
                        notifications.map((item) => (
                            <TouchableOpacity
                                key={item.id}
                                onPress={() => handleRead(item.id)}
                                activeOpacity={0.9}
                                className={`w-full relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14] ${item.isRead ? 'opacity-70' : ''}`}
                            >
                                {/* Unread Indicator */}
                                {!item.isRead && (
                                    <View
                                        className="absolute left-0 top-0 bottom-0 w-1 bg-primary"
                                        style={{ shadowColor: '#0d7ff2', shadowOpacity: 1, shadowRadius: 10, elevation: 5 }}
                                    />
                                )}

                                <View className="flex-row gap-4 p-4 items-start">
                                    {/* Icon */}
                                    <View
                                        className={`items-center justify-center w-12 h-12 rounded-lg border ${item.type === 'MAINTENANCE_ALERT' ? 'bg-primary/10 border-primary/20' :
                                            item.type === 'COMMUNITY_ALERT' ? 'bg-green-500/10 border-green-500/20' :
                                                'bg-white/5 border-white/10'
                                            }`}
                                    >
                                        <MaterialIcons
                                            name={
                                                item.type === 'MAINTENANCE_ALERT' ? 'build' :
                                                    item.type === 'COMMUNITY_ALERT' ? 'forum' : 'notifications'
                                            }
                                            size={24}
                                            color={
                                                item.type === 'MAINTENANCE_ALERT' ? '#0d7ff2' :
                                                    item.type === 'COMMUNITY_ALERT' ? '#22c55e' : '#9ca3af'
                                            }
                                        />
                                    </View>

                                    {/* Content */}
                                    <View className="flex-1 flex-col gap-1">
                                        <View className="flex-row justify-between items-start">
                                            <Text className={`text-lg font-bold leading-tight ${item.isRead ? 'text-gray-400' : 'text-white'}`}>
                                                {item.title}
                                            </Text>
                                            {!item.isRead && (
                                                <View className="bg-primary/10 px-2 py-0.5 rounded-full">
                                                    <Text className="text-primary text-xs font-medium">New</Text>
                                                </View>
                                            )}
                                        </View>
                                        <Text className="text-gray-300 text-sm font-normal leading-relaxed">
                                            {item.body}
                                        </Text>
                                        <Text className="text-[#9cabba] text-xs mt-2 font-medium">
                                            {formatDate(item.createdAt)}
                                        </Text>
                                    </View>
                                </View>
                            </TouchableOpacity>
                        ))
                    )}
                </ScrollView>
            </View>

        </SafeAreaView>
    );
}
