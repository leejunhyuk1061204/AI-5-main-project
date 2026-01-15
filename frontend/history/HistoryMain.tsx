import React from 'react';
import { View, Text, ScrollView, Platform, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import BottomNav from '../nav/BottomNav';
import Header from '../header/Header';

export default function HistoryMain() {
    const navigation = useNavigation();
    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Background Glows */}
            {/* Background Glows */}
            <View
                className="absolute -top-40 -right-40 w-96 h-96 bg-blue-900/10 rounded-full blur-3xl z-0"
                pointerEvents={Platform.OS === 'web' ? undefined : 'none'}
                style={Platform.OS === 'web' ? { pointerEvents: 'none' } : undefined}
            />
            <View
                className="absolute top-1/2 -left-40 w-80 h-80 bg-primary/10 rounded-full blur-3xl z-0"
                pointerEvents={Platform.OS === 'web' ? undefined : 'none'}
                style={Platform.OS === 'web' ? { pointerEvents: 'none' } : undefined}
            />

            <ScrollView
                className="flex-1"
                contentContainerStyle={{ paddingBottom: 100 }}
                showsVerticalScrollIndicator={false}
            >
                <Header />

                <View className="px-6 gap-5 pb-6 mt-4">
                    {/* Card 1: Driving History Analysis */}
                    <TouchableOpacity
                        onPress={() => navigation.navigate('DrivingHis' as never)}
                        className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-6 relative overflow-hidden active:bg-[#ffffff10]"
                    >
                        {/* Top Section */}
                        <View className="flex-row justify-between items-start mb-6">
                            <View className="flex-col gap-1">
                                <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start">
                                    <View className="w-1.5 h-1.5 rounded-full bg-primary" />
                                    <Text className="text-xs font-bold text-primary uppercase tracking-wider">Analysis</Text>
                                </View>
                                <Text className="text-lg font-bold text-white mt-2">주행 이력 분석</Text>
                                <Text className="text-sm font-medium text-gray-500 mt-0.5">최근 주행 기반 데이터</Text>
                            </View>
                            <View className="flex-col items-center justify-center mr-10">
                                <Text className="text-7xl font-bold text-primary tracking-tighter leading-none">
                                    98
                                </Text>
                                <Text className="text-xs text-white font-bold uppercase tracking-widest mt-1">Total Score</Text>
                            </View>
                        </View>

                        {/* Grid Section */}
                        <View className="flex-row gap-3 mt-4">
                            {/* Average Speed */}
                            <View className="flex-1 bg-[#1b2127] rounded-xl p-4 border border-white/10 flex-col gap-1">
                                <Text className="text-gray-400 text-sm font-medium mb-1">평균 속도</Text>
                                <View className="flex-row items-baseline gap-1">
                                    <Text className="text-xl font-bold text-white">42</Text>
                                    <Text className="text-xs text-gray-500 font-semibold">km/h</Text>
                                </View>
                            </View>
                            {/* Fuel Consumption */}
                            <View className="flex-1 bg-[#1b2127] rounded-xl p-4 border border-white/10 flex-col gap-1">
                                <Text className="text-gray-400 text-sm font-medium mb-1">소모 연료량</Text>
                                <View className="flex-row items-baseline gap-1">
                                    <Text className="text-xl font-bold text-white">4.2</Text>
                                    <Text className="text-xs text-gray-500 font-semibold">L</Text>
                                </View>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Card 2: Consumables Management */}
                    <TouchableOpacity
                        onPress={() => navigation.navigate('SupManage' as never)}
                        className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-6 relative overflow-hidden active:bg-[#ffffff10]"
                    >
                        <View className="flex-row justify-between items-center">
                            <View className="flex-col gap-1">
                                <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start">
                                    <MaterialIcons name="build" size={10} color="#0d7ff2" />
                                    <Text className="text-xs font-bold text-primary uppercase tracking-wider">Prediction</Text>
                                </View>
                                <Text className="text-lg font-bold text-white mt-2">소모품 관리 및 예지</Text>
                                <Text className="text-sm text-gray-400">엔진 오일 잔여 수명 예측</Text>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Card 3: Regular Inspection */}
                    <TouchableOpacity
                        onPress={() => navigation.navigate('RecallHis' as never)}
                        className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-6 relative overflow-hidden flex-row items-center justify-between active:bg-[#ffffff10]"
                    >
                        <View className="flex-col gap-1 z-10 flex-1">
                            <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 self-start mb-2">
                                <MaterialIcons name="verified-user" size={10} color="#0d7ff2" />
                                <Text className="text-sm font-bold text-primary uppercase tracking-wider">Official</Text>
                            </View>
                            <Text className="text-lg font-bold text-white">정기 검사 및 리콜</Text>
                            <Text className="text-sm text-gray-400">다음 정기 검사까지</Text>
                        </View>
                        <View className="relative flex-col items-center justify-center p-3">
                            <Text className="text-3xl font-extrabold text-white tracking-tight">D-14</Text>
                            <Text className="text-sm font-bold text-primary uppercase tracking-wider mt-1">Days left</Text>
                        </View>
                    </TouchableOpacity>
                </View>

            </ScrollView>

            <BottomNav />
        </SafeAreaView>
    );
}
