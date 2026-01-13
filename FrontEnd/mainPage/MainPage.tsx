import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
import { useNavigation } from '@react-navigation/native';
import BottomNav from '../nav/BottomNav';

const { width } = Dimensions.get('window');

export default function MainPage() {
    const navigation = useNavigation<any>();

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Main Content ScrollView */}
            {/* Added bottom padding for navigation bar space */}
            <ScrollView
                className="flex-1"
                contentContainerStyle={{ paddingBottom: 100 }}
                showsVerticalScrollIndicator={false}
            >

                {/* Header */}
                <View className="flex-row items-center justify-between px-6 pt-6 pb-2">
                    <View>
                        <TouchableOpacity onPress={() => navigation.navigate('Login')}>
                            <Text className="text-2xl font-bold text-primary tracking-tight">
                                로그인
                            </Text>
                        </TouchableOpacity>
                        <Text className="text-gray-400 text-xs mt-1">
                            Vehicle Status: Connected
                        </Text>
                    </View>
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center rounded-full bg-[#1b2127] border border-white/10 active:scale-95"
                        activeOpacity={0.7}
                    >
                        <MaterialIcons name="notifications-none" size={24} color="white" />
                    </TouchableOpacity>
                </View>

                {/* Car Info Card */}
                <View className="px-6 py-4">
                    <View className="relative overflow-hidden rounded-xl bg-[#ffffff08] border border-[#ffffff14] p-4 flex-row items-center justify-between shadow-lg">
                        {/* Background Glow simulation */}
                        <View className="absolute right-0 top-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />

                        <View className="flex-row items-center gap-4 z-10">
                            <View className="w-12 h-12 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center shadow-inner">
                                <MaterialIcons name="directions-car" size={24} color="#d1d5db" />
                            </View>
                            <View>
                                <Text className="text-white text-base font-bold leading-tight">현대 아반떼</Text>
                                <Text className="text-[#9cabba] text-sm font-normal">123가 4567</Text>
                            </View>
                        </View>

                        <TouchableOpacity className="flex-row items-center gap-1 bg-primary/10 px-3 py-1.5 rounded-full border border-primary/20 hover:bg-primary/20 z-10">
                            <Text className="text-primary text-sm font-bold">상세</Text>
                            <MaterialIcons name="chevron-right" size={16} color="#0d7ff2" />
                        </TouchableOpacity>
                    </View>
                </View>

                {/* Health Score Circular Chart */}
                <View className="items-center justify-center py-6 relative">
                    {/* Background Glow */}
                    <View className="absolute w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

                    <View className="relative w-64 h-64 items-center justify-center">
                        <Svg width="100%" height="100%" viewBox="0 0 100 100" className="-rotate-90">
                            <Defs>
                                <LinearGradient id="blueGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                    <Stop offset="0%" stopColor="#00f2fe" />
                                    <Stop offset="100%" stopColor="#0d7ff2" />
                                </LinearGradient>
                            </Defs>
                            {/* Background Circle */}
                            <Circle
                                cx="50"
                                cy="50"
                                r="42"
                                stroke="#1b2127"
                                strokeWidth="6"
                                fill="transparent"
                            />
                            {/* Progress Circle (approx 85% for 95 score look) */}
                            <Circle
                                cx="50"
                                cy="50"
                                r="42"
                                stroke="url(#blueGradient)"
                                strokeWidth="6"
                                fill="transparent"
                                strokeDasharray="264"
                                strokeDashoffset="13"
                                strokeLinecap="round"
                            />
                        </Svg>

                        <View className="absolute inset-0 items-center justify-center z-10">
                            <Text className="text-[#9cabba] text-sm font-medium tracking-wide mb-1">종합 점수</Text>
                            <Text className="text-6xl font-bold text-white tracking-tighter">
                                95<Text className="text-2xl text-gray-500 font-normal">점</Text>
                            </Text>

                            <View className="mt-3 flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-[#0bda5b]/10 border border-[#0bda5b]/20">
                                <View className="w-1.5 h-1.5 rounded-full bg-[#0bda5b]" />
                                <Text className="text-[#0bda5b] text-xs font-bold">상태 최상</Text>
                            </View>
                        </View>
                    </View>
                </View>

                {/* Status Grid */}
                <View className="px-6 mb-6">
                    <View className="flex-row items-center mb-4">
                        <Text className="text-white text-lg font-bold">실시간 상태</Text>
                        <View className="h-px bg-slate-800 flex-1 ml-4" />
                    </View>

                    <View className="flex-row gap-3">
                        {[
                            { label: '엔진', icon: 'settings', lib: MaterialIcons },
                            { label: '배터리', icon: 'battery-full', lib: MaterialIcons },
                            { label: '타이어', icon: 'car-repair', lib: MaterialIcons } // tire-repair not in basic material
                        ].map((item, index) => (
                            <TouchableOpacity
                                key={index}
                                className="flex-1 aspect-square rounded-xl bg-[#ffffff08] border border-[#ffffff14] items-center justify-center gap-3 active:bg-white/5"
                                activeOpacity={0.7}
                            >
                                <item.lib name={item.icon as any} size={32} color="#0d7ff2" style={{ textShadowColor: 'rgba(13, 127, 242, 0.5)', textShadowRadius: 10 }} />
                                <Text className="text-gray-300 text-sm font-medium">{item.label}</Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                </View>

                {/* AI Recommendation Card */}
                <View className="px-6 pb-4">
                    <View className="relative overflow-hidden rounded-xl border border-primary/30 p-5">
                        {/* Gradient Background - simulating bg-gradient-to-br from-[#111923] to-[#0D0D0D] */}
                        <View className="absolute inset-0 bg-slate-900" />
                        {/* Decorative blurs */}
                        <View className="absolute top-0 right-0 w-24 h-24 bg-primary/10 blur-2xl rounded-full" />
                        <View className="absolute bottom-0 left-0 w-20 h-20 bg-blue-500/5 blur-xl rounded-full" />

                        <View className="flex-row items-center justify-between mb-2">
                            <View className="flex-row items-center gap-2">
                                <MaterialIcons name="auto-awesome" size={18} color="#0d7ff2" />
                                <Text className="text-primary text-xs font-bold tracking-wider uppercase">AI 맞춤 권고</Text>
                            </View>
                            <View className="bg-red-500/20 px-2 py-0.5 rounded border border-red-500/20">
                                <Text className="text-xs font-bold text-red-400">D-15</Text>
                            </View>
                        </View>

                        <Text className="text-white text-lg font-bold mb-1">엔진오일 교체 15일 전</Text>
                        <Text className="text-[#9cabba] text-sm mb-4 leading-relaxed">
                            차량 데이터를 분석한 결과, 15일 내에 엔진오일을 교체하는 것이 권장됩니다.
                        </Text>

                        <TouchableOpacity
                            className="w-full py-3 bg-primary rounded-lg flex-row items-center justify-center gap-2 shadow-lg shadow-primary/30 active:bg-blue-600"
                            activeOpacity={0.8}
                        >
                            <Text className="text-white text-sm font-bold">예약하고 할인 받기</Text>
                            <MaterialIcons name="arrow-forward" size={16} color="white" />
                        </TouchableOpacity>
                    </View>
                </View>

            </ScrollView>

            <BottomNav />

        </SafeAreaView>
    );
}
