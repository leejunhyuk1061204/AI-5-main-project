import React from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import BottomNav from '../nav/BottomNav';

export default function AlertMain() {
    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Background Pattern (Simulated) */}
            <View className="absolute inset-0 z-0">
                <View className="absolute inset-0 bg-[#0c0e12]" />
                {/* Checkered pattern simulation - Removed invalid web styles */}
                <View className="absolute inset-0 bg-[#0c0e12]" />
            </View>

            {/* Glow Effects */}
            {/* Glow Effects */}
            <View
                className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-3xl z-0"
                pointerEvents={Platform.OS === 'web' ? undefined : 'none'}
                style={Platform.OS === 'web' ? { pointerEvents: 'none' } : undefined}
            />
            <View
                className="absolute bottom-0 left-0 w-64 h-64 bg-blue-900/10 rounded-full blur-3xl z-0"
                pointerEvents={Platform.OS === 'web' ? undefined : 'none'}
                style={Platform.OS === 'web' ? { pointerEvents: 'none' } : undefined}
            />


            {/* Main Content */}
            <View className="flex-1 z-10">
                {/* Header */}
                <View className="px-6 py-5 flex-row items-center justify-between border-b border-white/5 bg-[#0c0e12]/80 backdrop-blur-md">
                    <Text className="text-white text-2xl font-bold tracking-tight">알림 센터</Text>
                    <TouchableOpacity className="flex-row items-center justify-center rounded-full px-3 py-1.5 active:bg-primary/10">
                        <MaterialIcons name="done-all" size={18} color="#0d7ff2" style={{ marginRight: 4 }} />
                        <Text className="text-xs font-bold text-primary">모두 읽음</Text>
                    </TouchableOpacity>
                </View>

                {/* Notification List */}
                <ScrollView
                    className="flex-1 p-5"
                    contentContainerStyle={{ paddingBottom: 100, gap: 16 }}
                    showsVerticalScrollIndicator={false}
                >
                    {/* Unread: Critical Alert */}
                    <TouchableOpacity activeOpacity={0.9} className="w-full relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14]">
                        {/* Unread Indicator */}
                        <View className="absolute left-0 top-0 bottom-0 w-1 bg-primary" style={{ shadowColor: '#0d7ff2', shadowOpacity: 1, shadowRadius: 10, elevation: 5 }} />

                        <View className="flex-row gap-4 p-4 items-start">
                            {/* Icon */}
                            <View className="relative items-center justify-center w-12 h-12 rounded-lg bg-red-500/10 border border-red-500/20"
                                style={{ shadowColor: 'rgba(239, 68, 68, 0.5)', shadowOpacity: 0.3, shadowRadius: 10 }}>
                                <MaterialIcons name="warning" size={24} color="#ef4444" />
                            </View>
                            {/* Content */}
                            <View className="flex-1 flex-col gap-1">
                                <View className="flex-row justify-between items-start">
                                    <Text className="text-white text-lg font-bold leading-tight">이상 감지</Text>
                                    <View className="bg-primary/10 px-2 py-0.5 rounded-full">
                                        <Text className="text-primary text-xs font-medium">중요</Text>
                                    </View>
                                </View>
                                <Text className="text-gray-300 text-sm font-normal leading-relaxed">배터리 전압이 불안정합니다. 점검이 필요합니다.</Text>
                                <Text className="text-[#9cabba] text-xs mt-2 font-medium">방금 전</Text>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Unread: Maintenance Alert */}
                    <TouchableOpacity activeOpacity={0.9} className="w-full relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14]">
                        {/* Unread Indicator */}
                        <View className="absolute left-0 top-0 bottom-0 w-1 bg-primary" style={{ shadowColor: '#0d7ff2', shadowOpacity: 1, shadowRadius: 10, elevation: 5 }} />

                        <View className="flex-row gap-4 p-4 items-start">
                            <View className="items-center justify-center w-12 h-12 rounded-lg bg-primary/10 border border-primary/20"
                                style={{ shadowColor: 'rgba(13, 127, 242, 0.4)', shadowOpacity: 0.3, shadowRadius: 10 }}>
                                <MaterialCommunityIcons name="oil" size={24} color="#0d7ff2" />
                            </View>
                            <View className="flex-1 flex-col gap-1">
                                <Text className="text-white text-lg font-bold leading-tight">소모품 교체</Text>
                                <Text className="text-gray-300 text-sm font-normal leading-relaxed">엔진오일 교체 주기가 500km 남았습니다.</Text>
                                <Text className="text-[#9cabba] text-xs mt-2 font-medium">1시간 전</Text>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Read: Recall Info */}
                    <TouchableOpacity activeOpacity={0.9} className="w-full relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14] opacity-90">
                        <View className="flex-row gap-4 p-4 items-start">
                            <View className="items-center justify-center w-12 h-12 rounded-lg bg-white/5 border border-white/10">
                                <MaterialIcons name="fact-check" size={24} color="#9ca3af" />
                            </View>
                            <View className="flex-1 flex-col gap-1">
                                <Text className="text-gray-200 text-lg font-bold leading-tight">리콜 정보</Text>
                                <Text className="text-[#9cabba] text-sm font-normal leading-relaxed">새로운 리콜 정보가 등록되었습니다. 상세 내용을 확인하세요.</Text>
                                <Text className="text-[#5f6d7e] text-xs mt-2 font-medium">1일 전</Text>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Read: Tire Pressure */}
                    <TouchableOpacity activeOpacity={0.9} className="w-full relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14] opacity-90">
                        <View className="flex-row gap-4 p-4 items-start">
                            <View className="items-center justify-center w-12 h-12 rounded-lg bg-white/5 border border-white/10">
                                <MaterialCommunityIcons name="car-tire-alert" size={24} color="#9ca3af" />
                            </View>
                            <View className="flex-1 flex-col gap-1">
                                <Text className="text-gray-200 text-lg font-bold leading-tight">타이어 공기압 정상</Text>
                                <Text className="text-[#9cabba] text-sm font-normal leading-relaxed">정기 점검 결과 모든 타이어 공기압이 정상 범위입니다.</Text>
                                <Text className="text-[#5f6d7e] text-xs mt-2 font-medium">3일 전</Text>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Read: Weekly Report */}
                    <TouchableOpacity activeOpacity={0.9} className="w-full relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14] opacity-90">
                        <View className="flex-row gap-4 p-4 items-start">
                            <View className="items-center justify-center w-12 h-12 rounded-lg bg-white/5 border border-white/10">
                                <MaterialIcons name="insights" size={24} color="#9ca3af" />
                            </View>
                            <View className="flex-1 flex-col gap-1">
                                <Text className="text-gray-200 text-lg font-bold leading-tight">주간 주행 리포트</Text>
                                <Text className="text-[#9cabba] text-sm font-normal leading-relaxed">지난주 주행 거리와 연비 분석 리포트가 생성되었습니다.</Text>
                                <Text className="text-[#5f6d7e] text-xs mt-2 font-medium">1주 전</Text>
                            </View>
                        </View>
                    </TouchableOpacity>

                    <View className="flex-row justify-center py-4">
                        <Text className="text-[#5f6d7e] text-xs">최근 30일간의 알림이 표시됩니다.</Text>
                    </View>
                </ScrollView>
            </View>

            <BottomNav />
        </SafeAreaView>
    );
}
