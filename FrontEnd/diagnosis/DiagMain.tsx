import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, Dimensions, StyleSheet } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import BottomNav from '../nav/BottomNav';

const { width } = Dimensions.get('window');

export default function DiagMain() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();

    return (
        <View className="flex-1 bg-[#101922]">
            <StatusBar style="light" />

            {/* Background Effects matching MainPage */}
            {/* Subtle top glow */}
            <View className="absolute top-0 left-0 right-0 h-[400px] bg-primary/5 blur-3xl rounded-b-full pointer-events-none" />

            {/* content inside safe area */}
            <View style={{ paddingTop: insets.top, flex: 1 }}>

                {/* Header */}
                <View className="relative z-10 flex-row items-center justify-between px-6 py-4 pb-2">
                    <View className="w-10" />
                    <Text className="text-white text-lg font-bold tracking-wider text-center flex-1 uppercase">
                        진단 센터
                    </Text>
                    <TouchableOpacity className="w-10 items-end justify-center">
                        <View className="relative">
                            <View className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full z-10 border border-[#101922]" />
                            <MaterialIcons name="notifications-none" size={24} color="white" />
                        </View>
                    </TouchableOpacity>
                </View>

                {/* Status Pill - Kept but styled to match theme */}
                <View className="relative z-10 items-center justify-center my-4 mb-6">
                    <View className="flex-row items-center gap-3 rounded-full bg-[#1b2127]/90 border border-white/10 pl-4 pr-5 py-2 shadow-lg backdrop-blur-md">
                        <View className="relative items-center justify-center w-3 h-3">
                            <View className="absolute w-2.5 h-2.5 rounded-full bg-primary opacity-50 animate-pulse" />
                            <View className="w-2 h-2 rounded-full bg-primary shadow-sm" />
                        </View>
                        <View className="flex-row items-center gap-2">
                            <MaterialCommunityIcons name="bluetooth-connect" size={18} color="#0d7ff2" />
                            <Text className="text-xs font-medium text-gray-300 tracking-wide">
                                OBD-II 연결됨 <Text className="text-gray-600 mx-1">|</Text> <Text className="text-white font-bold">GV80</Text>
                            </Text>
                        </View>
                    </View>
                </View>

                {/* Main Content Grid */}
                <ScrollView
                    className="flex-1 px-5"
                    contentContainerStyle={{ paddingBottom: 100 }}
                    showsVerticalScrollIndicator={false}
                >
                    <View className="flex-col gap-4">

                        {/* Row 1: Real-time Monitoring */}
                        <TouchableOpacity
                            className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-5 mb-0 active:bg-white/5 items-start justify-between min-h-[140px]"
                            style={styles.techCard}
                            activeOpacity={0.9}
                        >
                            <View className="flex-row justify-between items-start w-full mb-6">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center">
                                    <MaterialIcons name="insights" size={24} color="#0d7ff2" />
                                </View>
                                <MaterialIcons name="arrow-forward" size={20} color="#6b7280" />
                            </View>
                            <View>
                                <Text className="text-base font-bold text-white mb-1">실시간 모니터링</Text>
                                <Text className="text-[11px] font-normal text-gray-400 tracking-wide">엔진/미션 데이터 스트리밍</Text>
                            </View>
                        </TouchableOpacity>

                        {/* Featured: AI Pro Diagnosis */}
                        <TouchableOpacity
                            className="w-full relative overflow-hidden rounded-2xl p-5 min-h-[160px] justify-between border border-[#ffffff14] bg-[#ffffff08]"
                            activeOpacity={0.9}
                            onPress={() => navigation.navigate('ActiveLoading')}
                        >
                            {/* Blue Glow Effect - Subtle */}
                            <View className="absolute -top-12 -right-12 w-40 h-40 bg-primary/10 blur-3xl rounded-full" />

                            <View className="relative z-10 flex-row justify-between items-start w-full mb-6">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center shadow-md">
                                    <MaterialCommunityIcons name="robot" size={24} color="#0d7ff2" />
                                </View>
                                <View className="px-2 py-0.5 rounded bg-primary/10 border border-primary/20">
                                    <Text className="text-[9px] font-bold text-primary tracking-wider">AI PRO</Text>
                                </View>
                            </View>

                            <View className="relative z-10">
                                <Text className="text-base font-bold text-white mb-1">AI 복합 진단</Text>
                                <Text className="text-[11px] font-normal text-gray-400 tracking-wide">소리, 사진, 데이터 통합 분석</Text>
                            </View>
                        </TouchableOpacity>

                        {/* Row 2: DTC Scan */}
                        <TouchableOpacity
                            className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-5 active:bg-white/5 items-start justify-between min-h-[140px]"
                            style={styles.techCard}
                            activeOpacity={0.9}
                        >
                            <View className="flex-row justify-between items-start w-full mb-6">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center">
                                    <MaterialIcons name="car-crash" size={24} color="#0d7ff2" />
                                </View>
                                <MaterialIcons name="arrow-forward" size={20} color="#6b7280" />
                            </View>
                            <View>
                                <Text className="text-base font-bold text-white mb-1">고장 코드(DTC) 스캔</Text>
                                <Text className="text-[11px] font-normal text-gray-400 tracking-wide">ECU 전체 시스템 점검</Text>
                            </View>
                        </TouchableOpacity>

                        {/* Row 2: Specs */}
                        <TouchableOpacity
                            className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-5 active:bg-white/5 items-start justify-between min-h-[140px]"
                            style={styles.techCard}
                            activeOpacity={0.9}
                        >
                            <View className="flex-row justify-between items-start w-full mb-6">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center">
                                    <MaterialIcons name="fact-check" size={24} color="#0d7ff2" />
                                </View>
                                <MaterialIcons name="arrow-forward" size={20} color="#6b7280" />
                            </View>
                            <View>
                                <Text className="text-base font-bold text-white mb-1">차량 상세 제원</Text>
                                <Text className="text-[11px] font-normal text-gray-400 tracking-wide">제조사 공식 데이터베이스</Text>
                            </View>
                        </TouchableOpacity>

                    </View>

                    {/* Add New Vehicle Button */}
                    <View className="mt-6 mb-8">
                        <TouchableOpacity
                            className="w-full rounded-2xl border border-dashed border-[#ffffff14] bg-[#ffffff05] p-4 flex-row items-center justify-center gap-3 active:bg-white/5"
                            activeOpacity={0.8}
                            onPress={() => navigation.navigate('PassiveReg')}
                        >
                            <MaterialIcons name="add-circle-outline" size={20} color="#6b7280" />
                            <Text className="text-sm font-medium text-gray-400 tracking-wide">새 차량 등록하기</Text>
                        </TouchableOpacity>
                    </View>
                </ScrollView>
            </View>

            <BottomNav />
        </View>
    );
}

const styles = StyleSheet.create({
    techCard: {
        shadowColor: "#000",
        shadowOffset: {
            width: 0,
            height: 4,
        },
        shadowOpacity: 0.3,
        shadowRadius: 4.65,
        elevation: 8,
    }
});
