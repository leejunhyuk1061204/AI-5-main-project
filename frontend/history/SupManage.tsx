import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

export default function SupManage() {
    const navigation = useNavigation();

    const consumables = [
        {
            title: "브레이크 패드",
            status: "즉시 교체 요망",
            percentage: 12,
            icon: "disc-full",
            iconFamily: "MaterialIcons",
            color: "#ef4444", // Danger
            message: "안전을 위해 지금 정비소를 예약하세요.",
            messageIcon: "smart-toy",
            glow: "shadow-red-500/20"
        },
        {
            title: "타이어",
            status: "마모 진행 중 · 점검 권장",
            percentage: 45,
            icon: "car-tire-alert",
            iconFamily: "MaterialCommunityIcons",
            color: "#f59e0b", // Warning
            message: "예상 교체 시기: 6개월 이내 (AI 예측)",
            messageIcon: "smart-toy",
            glow: "shadow-amber-500/20"
        },
        {
            title: "엔진 오일",
            status: "상태 양호",
            percentage: 78,
            icon: "oil",
            iconFamily: "MaterialCommunityIcons",
            color: "#0d7ff2", // Primary
            message: "교체까지 약 8,200km 남음",
            messageIcon: "smart-toy",
            glow: "shadow-blue-500/20"
        },
        {
            title: "에어 필터",
            status: "상태 매우 좋음",
            percentage: 90,
            icon: "air-filter",
            iconFamily: "MaterialCommunityIcons",
            color: "#0d7ff2", // Primary
            message: "다음 엔진 오일 교체 시 함께 점검하세요.",
            messageIcon: "smart-toy",
            glow: "shadow-blue-500/20"
        },
        {
            title: "배터리",
            status: "전압 안정적",
            percentage: 95,
            icon: "battery-charging-full",
            iconFamily: "MaterialIcons",
            color: "#0d7ff2", // Primary
            message: "최근 충전 효율이 98%로 매우 높습니다.",
            messageIcon: "smart-toy",
            glow: "shadow-blue-500/20"
        }
    ];

    const renderIcon = (item: any) => {
        if (item.iconFamily === "MaterialCommunityIcons") {
            return <MaterialCommunityIcons name={item.icon as any} size={24} color={item.color} />;
        }
        return <MaterialIcons name={item.icon as any} size={24} color={item.color} />;
    };

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Background Gradients */}
            <View className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-primary/10 rounded-full blur-[100px]" />
            <View className="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] bg-[#151b2e] rounded-full blur-[100px] opacity-60" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-800 bg-[#101922]/95">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">소모품 관리</Text>
                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800">
                    <MaterialIcons name="more-vert" size={24} color="white" />
                </TouchableOpacity>
            </View>

            <ScrollView className="flex-1 px-6 pt-2" contentContainerStyle={{ paddingBottom: 100 }}>
                <View className="gap-4">
                    {consumables.map((item, index) => (
                        <View
                            key={index}
                            className="bg-[#ffffff05] border border-white/10 rounded-2xl p-4 overflow-hidden relative"
                        >
                            {/* Side Color Bar */}
                            <View
                                className="absolute left-0 top-0 bottom-0 w-1.5"
                                style={{ backgroundColor: item.color, shadowColor: item.color, shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.5, shadowRadius: 10, elevation: 5 }}
                            />

                            {/* Top Section */}
                            <View className="flex-row justify-between items-start mb-4 pl-3">
                                <View className="flex-row items-center gap-3">
                                    <View
                                        className="w-12 h-12 rounded-xl items-center justify-center border"
                                        style={{ backgroundColor: `${item.color}15`, borderColor: `${item.color}30` }}
                                    >
                                        {renderIcon(item)}
                                    </View>
                                    <View>
                                        <Text className="text-base font-bold text-white mb-0.5">
                                            {item.title}
                                        </Text>
                                        <Text
                                            className="text-xs font-medium"
                                            style={{ color: item.percentage <= 20 ? item.color : '#9ca3af' }}
                                        >
                                            {item.status}
                                        </Text>
                                    </View>
                                </View>
                                <Text
                                    className="text-xl font-bold"
                                    style={{ color: item.percentage <= 20 || item.percentage <= 50 ? item.color : 'white' }}
                                >
                                    {item.percentage}%
                                </Text>
                            </View>

                            {/* Progress Bar & Message */}
                            <View className="pl-3">
                                <View className="w-full bg-gray-800/50 rounded-full h-1.5 mb-3 overflow-hidden">
                                    <View
                                        className="h-1.5 rounded-full"
                                        style={{
                                            width: `${item.percentage}%`,
                                            backgroundColor: item.color,
                                            shadowColor: item.color,
                                            shadowOffset: { width: 0, height: 0 },
                                            shadowOpacity: 0.5,
                                            shadowRadius: 8
                                        }}
                                    />
                                </View>
                                <View className="flex-row items-center gap-2 bg-black/20 p-3 rounded-xl border border-white/5">
                                    <MaterialIcons
                                        name={item.messageIcon as any}
                                        size={16}
                                        color={item.color}
                                    />
                                    <Text className="text-xs text-gray-400 flex-1">
                                        {item.message}
                                    </Text>
                                </View>
                            </View>
                        </View>
                    ))}
                </View>
            </ScrollView>


        </SafeAreaView>
    );
}
