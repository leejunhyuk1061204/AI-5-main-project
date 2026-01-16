import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, Animated } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';

export default function RecallHis() {
    const navigation = useNavigation();

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 h-14 border-b border-white/5 bg-[#1B222D]/60">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="flex items-center justify-center w-10 h-10 rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-base font-bold text-white">리콜 기록</Text>
                <View className="w-10" />
            </View>

            <ScrollView className="flex-1 px-4 pt-6" contentContainerStyle={{ paddingBottom: 100 }}>
                {/* Next Inspection Card */}
                <View className="relative mb-8">
                    {/* Glow Effect Background Removed */}

                    <View className="bg-surface-dark border border-white/10 rounded-2xl p-6 shadow-lg overflow-hidden">
                        {/* Decorative Background Elements Removed */}

                        <View className="relative z-10 gap-4">
                            <View className="flex-row justify-between items-start">
                                <View className="gap-1">
                                    <Text className="text-slate-400 text-xs font-medium uppercase tracking-wider">
                                        Next Inspection
                                    </Text>
                                    <Text className="text-white text-lg font-bold">
                                        차기 정기 검사
                                    </Text>
                                </View>
                                <View className="bg-primary/10 px-3 py-1 rounded-full border border-primary/20">
                                    <Text className="text-primary text-xs font-bold">
                                        검사 기간입니다
                                    </Text>
                                </View>
                            </View>

                            <View className="flex-row items-end gap-2 mt-2">
                                <Text className="text-6xl font-bold text-white tracking-tighter">
                                    D-24
                                </Text>
                                <Text className="text-slate-400 text-sm font-medium pb-2">
                                    일 남음
                                </Text>
                            </View>

                            <View className="flex-row items-center gap-2 mt-2 pt-4 border-t border-white/5">
                                <MaterialIcons name="calendar-today" size={16} color="#64748b" />
                                <Text className="text-slate-300 text-sm">
                                    2024.12.15 까지
                                </Text>
                            </View>

                            {/* Progress Bar */}
                            <View className="w-full bg-slate-800 rounded-full h-1.5 mt-1 overflow-hidden">
                                <View
                                    className="bg-primary h-1.5 rounded-full shadow-[0_0_10px_rgba(13,127,242,0.8)]"
                                    style={{ width: '75%' }}
                                />
                            </View>
                        </View>
                    </View>
                </View>

                {/* Urgent Recall Items Section */}
                <View className="gap-4">
                    <View className="flex-row items-center justify-between px-1">
                        <View className="flex-row items-center gap-1">
                            <Text className="text-white font-bold text-lg">
                                긴급 리콜 항목
                            </Text>
                            <View className="w-2 h-2 rounded-full bg-status-error ml-1" />
                        </View>
                        <Text className="text-xs text-slate-500">
                            최근 업데이트: 오늘 09:00
                        </Text>
                    </View>

                    {/* Recall Item Card */}
                    <TouchableOpacity className="relative bg-[#1B222D] active:bg-[#252e3e] border border-white/10 rounded-xl overflow-hidden shadow-md">
                        <View className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#E04F5F]" />
                        <View className="p-5 gap-4">
                            <View>
                                <View className="flex-row items-center gap-2 mb-3">
                                    <View className="px-2 py-1 rounded bg-[#E04F5F]/15 border border-[#E04F5F]/30">
                                        <Text className="text-[11px] font-bold text-[#E04F5F]">
                                            수리 필요
                                        </Text>
                                    </View>
                                    <Text className="text-slate-500 text-xs">
                                        Code: RC-2024-001
                                    </Text>
                                </View>
                                <Text className="text-white font-bold text-[17px] leading-snug mb-2">
                                    고압 연료 펌프 관련 리콜
                                </Text>
                                <Text className="text-slate-400 text-[13px] leading-5" numberOfLines={2}>
                                    연료 펌프 내부 부품 마모로 인한 시동 꺼짐 가능성이 확인되어 교체가 필요합니다.
                                </Text>
                            </View>

                            <View className="flex-row mt-1">
                                <View className="flex-row items-center gap-2 px-5 py-3 rounded-xl bg-[#2C3542] active:bg-[#3A4655]">
                                    <Text className="text-white text-[13px] font-semibold">상세 보기</Text>
                                    <MaterialIcons name="arrow-forward" size={16} color="white" />
                                </View>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Load More Button */}
                    <TouchableOpacity className="flex-row items-center justify-center gap-1 mt-4 py-2">
                        <Text className="text-slate-500 text-sm font-medium">
                            이전 기록 더보기
                        </Text>
                        <MaterialIcons name="expand-more" size={18} color="#64748b" />
                    </TouchableOpacity>
                </View>
            </ScrollView>

            {/* Floating Action Button */}
            <View className="absolute bottom-6 right-6">
                <TouchableOpacity
                    className="items-center justify-center w-14 h-14 bg-primary rounded-full shadow-lg shadow-blue-500/40 active:scale-95"
                >
                    <MaterialIcons name="add" size={28} color="white" />
                </TouchableOpacity>
            </View>
        </SafeAreaView>
    );
}
