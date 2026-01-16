import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Platform, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import Svg, { Circle, Path, Defs, LinearGradient, Stop } from 'react-native-svg';
import { LinearGradient as ExpoLinearGradient } from 'expo-linear-gradient';


const { width } = Dimensions.get('window');

// Custom colors from the design
const COLORS = {
    primary: "#0d7ff2",
    backgroundDark: "#10151A",
    surfaceDark: "#161F29",
    success: "#0bda5b",
    accentBlue: "#1E90FF",
    textWhite: "#FFFFFF",
    textGray: "#9CA3AF"
};

export default function DrivingHis() {
    const navigation = useNavigation();

    // Animation for the pulsing dot - Removed as per request


    return (
        <SafeAreaView className="flex-1 bg-[#10151A]">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-800 bg-[#10151A]/95">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">주행 이력 분석</Text>
                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full active:bg-gray-800">
                    <MaterialIcons name="more-vert" size={24} color="white" />
                </TouchableOpacity>
            </View>

            <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
                <View className="p-4 gap-6 pb-8">

                    {/* Score Section */}
                    <View className="items-center justify-center py-6 relative">
                        {/* Background mesh effect approximation */}
                        <View className="absolute inset-0 opacity-10" style={{
                            backgroundColor: 'transparent',
                            // In RN, we can't easily do the radial gradient grid pattern without an image.
                            // We'll skip the grid pattern for now or could use a repeated image if provided.
                        }} />

                        <Text className="text-gray-400 text-xs font-medium tracking-widest uppercase mb-6">종합 안전 점수</Text>

                        <View className="relative w-64 h-64 justify-center items-center">
                            {/* Rotating dashed border simulation - omitted complex animation for stability, keeping static for now or simple spin */}
                            <View className="absolute inset-0 rounded-full border border-gray-800 border-dashed" style={{ opacity: 0.5 }} />

                            <Svg height="250" width="250" viewBox="0 0 100 100" style={{ transform: [{ rotate: '-90deg' }] }}>
                                {/* Background Circle */}
                                <Circle
                                    cx="50"
                                    cy="50"
                                    r="40"
                                    stroke="#161F29"
                                    strokeWidth="8"
                                    fill="transparent"
                                />
                                {/* Progress Circle */}
                                <Circle
                                    cx="50"
                                    cy="50"
                                    r="40"
                                    stroke="#0d7ff2"
                                    strokeWidth="8"
                                    fill="transparent"
                                    strokeDasharray="251.2"
                                    strokeDashoffset="20" // 92% approximation
                                    strokeLinecap="round"
                                />
                            </Svg>

                            <View className="absolute inset-0 items-center justify-center">
                                <Text className="text-6xl font-bold text-white tracking-tighter" style={{ textShadowColor: 'rgba(13, 127, 242, 0.5)', textShadowOffset: { width: 0, height: 0 }, textShadowRadius: 10 }}>92</Text>
                                <Text className="text-[#0d7ff2] text-sm font-bold mt-1 tracking-widest uppercase">최우수 등급</Text>
                            </View>

                            {/* Bottom Glow Line Removed */}
                        </View>

                        {/* Stats Row */}
                        <View className="flex-row justify-between w-full max-w-[300px] mt-6 px-4">
                            <View className="items-center">
                                <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">주행 거리</Text>
                                <Text className="text-lg font-bold text-white">1,240 <Text className="text-xs text-gray-400 font-normal">km</Text></Text>
                            </View>
                            <View className="w-px h-10 bg-gray-800" />
                            <View className="items-center">
                                <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">안전 운행</Text>
                                <Text className="text-lg font-bold text-[#0bda5b]">98%</Text>
                            </View>
                            <View className="w-px h-10 bg-gray-800" />
                            <View className="items-center">
                                <Text className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">연비 효율</Text>
                                <Text className="text-lg font-bold text-[#1E90FF]">14.2 <Text className="text-xs text-gray-400 font-normal">km/L</Text></Text>
                            </View>
                        </View>
                    </View>

                    {/* Chart Section */}
                    <View className="bg-[#161F29] border border-gray-800 rounded-xl p-5 overflow-hidden">
                        <View className="flex-row justify-between items-center mb-6">
                            <Text className="text-white text-base font-bold">주간 안전 지수 변화</Text>
                            <View className="bg-[#0d7ff2]/20 border border-[#0d7ff2]/30 px-2 py-1 rounded">
                                <Text className="text-xs text-[#0d7ff2]">이번주</Text>
                            </View>
                        </View>

                        <View className="h-40 w-full relative">
                            {/* Grid Lines */}
                            <View className="absolute inset-0 justify-between py-2">
                                <View className="w-full h-px bg-gray-800/50" />
                                <View className="w-full h-px bg-gray-800/50" />
                                <View className="w-full h-px bg-gray-800/50" />
                                <View className="w-full h-px bg-gray-800/50" />
                            </View>

                            <Svg height="100%" width="100%" preserveAspectRatio="none">
                                <Defs>
                                    <LinearGradient id="gradientArea" x1="0" x2="0" y1="0" y2="1">
                                        <Stop offset="0%" stopColor="#0d7ff2" stopOpacity="0.3" />
                                        <Stop offset="100%" stopColor="#0d7ff2" stopOpacity="0" />
                                    </LinearGradient>
                                </Defs>
                                {/* Area Path */}
                                <Path
                                    d="M0,100 L0,60 L50,40 L100,50 L150,20 L200,90 L250,90 L300,90 L300,100 Z" // Adjusted simplified coordinates for RN viewbox scaling
                                    fill="url(#gradientArea)"
                                    opacity={0.5}
                                />
                                {/* Line Path */}
                                <Path
                                    d="M0,60 L50,40 L100,50 L150,20 L200,90 L250,90 L300,90"
                                    stroke="#0d7ff2"
                                    strokeWidth="3"
                                    fill="none"
                                />
                                {/* Dots */}
                                <Circle cx="50" cy="40" r="3" fill="#161F29" stroke="#0d7ff2" strokeWidth="2" />
                                <Circle cx="100" cy="50" r="3" fill="#161F29" stroke="#0d7ff2" strokeWidth="2" />
                                <Circle cx="150" cy="20" r="3" fill="#161F29" stroke="#0d7ff2" strokeWidth="2" />
                            </Svg>



                            <View className="absolute bottom-0 left-0 right-0 top-0 pt-2 flex-row items-end justify-between pb-1">
                                <Text className="text-[10px] text-gray-500 w-8 text-center">월</Text>
                                <Text className="text-[10px] text-gray-500 w-8 text-center">화</Text>
                                <Text className="text-[10px] text-gray-500 w-8 text-center">수</Text>
                                <Text className="text-[10px] text-white font-bold w-8 text-center">목</Text>
                                <Text className="text-[10px] text-gray-500 opacity-50 w-8 text-center">금</Text>
                                <Text className="text-[10px] text-gray-500 opacity-50 w-8 text-center">토</Text>
                                <Text className="text-[10px] text-gray-500 opacity-50 w-8 text-center">일</Text>
                            </View>
                        </View>
                    </View>

                    {/* Recent History Section */}
                    <View>
                        <View className="flex-row items-center justify-between mb-4 px-1">
                            <Text className="text-white text-lg font-bold">최근 주행 기록</Text>
                            <TouchableOpacity>
                                <Text className="text-[#0d7ff2] text-sm font-medium">전체보기</Text>
                            </TouchableOpacity>
                        </View>

                        <View className="bg-[#161F29] rounded-xl border border-[#0d7ff2]/30 p-4 relative overflow-hidden">
                            {/* Gradient Background Effect Removed */}

                            <View className="flex-row justify-between items-center mb-4">
                                <View className="flex-row items-center gap-3">
                                    <View className="bg-[#0d7ff2]/10 p-2 rounded-full border border-[#0d7ff2]/20">
                                        <MaterialIcons name="commute" size={24} color="#0d7ff2" />
                                    </View>
                                    <Text className="text-white font-bold text-lg">2023.10.26 (목)</Text>
                                </View>
                                <View className="flex-row items-center gap-1 bg-gray-800/50 px-2 py-1 rounded border border-gray-700">
                                    <View className="w-2 h-2 rounded-full bg-[#0bda5b]" style={{ shadowColor: '#0bda5b', shadowOpacity: 0.5, shadowRadius: 5 }} />
                                    <Text className="text-xs font-medium text-gray-300">안전</Text>
                                </View>
                            </View>

                            <View className="flex-row flex-wrap gap-3">
                                <View className="flex-1 min-w-[45%] bg-[#10151A]/50 p-3 rounded-lg border border-gray-800">
                                    <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">주행 거리</Text>
                                    <Text className="text-white font-medium text-base">18.2 <Text className="text-xs text-gray-400">km</Text></Text>
                                </View>
                                <View className="flex-1 min-w-[45%] bg-[#10151A]/50 p-3 rounded-lg border border-gray-800">
                                    <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">주행 시간</Text>
                                    <Text className="text-white font-medium text-base">42 <Text className="text-xs text-gray-400">분</Text></Text>
                                </View>
                                <View className="flex-1 min-w-[45%] bg-[#10151A]/50 p-3 rounded-lg border border-gray-800 flex-row justify-between items-center">
                                    <View>
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">급가속</Text>
                                        <Text className="text-gray-300 font-medium text-base">0 <Text className="text-xs text-gray-500">회</Text></Text>
                                    </View>
                                    <MaterialIcons name="speed" size={20} color="#4B5563" />
                                </View>
                                <View className="flex-1 min-w-[45%] bg-[#10151A]/50 p-3 rounded-lg border border-gray-800 flex-row justify-between items-center">
                                    <View>
                                        <Text className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">급제동</Text>
                                        <Text className="text-gray-300 font-medium text-base">0 <Text className="text-xs text-gray-500">회</Text></Text>
                                    </View>
                                    <MaterialIcons name="warning" size={20} color="#4B5563" />
                                </View>
                            </View>
                        </View>
                    </View>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}
