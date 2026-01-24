import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, Dimensions, StyleSheet, Animated, Easing } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import Header from '../header/Header';
import BottomNav from '../nav/BottomNav';

const { width } = Dimensions.get('window');

export default function DiagMain() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const pulseAnim = React.useRef(new Animated.Value(1)).current;

    React.useEffect(() => {
        Animated.loop(
            Animated.sequence([
                Animated.timing(pulseAnim, {
                    toValue: 2,
                    duration: 1000,
                    useNativeDriver: true,
                    easing: Easing.inOut(Easing.ease),
                }),
                Animated.timing(pulseAnim, {
                    toValue: 1,
                    duration: 1000,
                    useNativeDriver: true,
                    easing: Easing.inOut(Easing.ease),
                }),
            ])
        ).start();
    }, []);

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />
            <View style={{ paddingTop: insets.top, flex: 1 }}>
                <Header />
                <View className="relative z-10 items-center justify-center my-4 mb-6">
                    <View className="flex-row items-center gap-3 rounded-full bg-[#1b2127]/90 border border-white/10 pl-4 pr-5 py-2 shadow-lg backdrop-blur-md">
                        <View className="relative items-center justify-center w-3 h-3">
                            <Animated.View style={{ opacity: pulseAnim, transform: [{ scale: pulseAnim }], }} className="absolute w-full h-full rounded-full bg-primary" />
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
                <ScrollView className="flex-1 px-5" contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
                    <View className="flex-col gap-4">
                        <TouchableOpacity className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-5 active:bg-white/5 items-start justify-between min-h-[120px] overflow-hidden relative" style={styles.techCard} activeOpacity={0.9} onPress={() => navigation.navigate('AiCompositeDiag')}>
                            <View className="flex-row justify-between items-start w-full mb-3 z-10">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center shadow-md">
                                    <MaterialCommunityIcons name="robot" size={24} color="#0d7ff2" />
                                </View>
                                <View className="px-2 py-0.5 rounded bg-primary/10 border border-primary/20">
                                    <Text className="text-xs font-bold text-primary tracking-wider">AI PRO</Text>
                                </View>
                            </View>
                            <View className="relative z-10">
                                <Text className="text-lg font-bold text-white mb-1">AI 복합 진단</Text>
                                <Text className="text-sm font-normal text-gray-400 tracking-wide">소리, 사진, 데이터 통합 분석</Text>
                            </View>
                        </TouchableOpacity>
                        <TouchableOpacity className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-5 mb-0 active:bg-white/5 items-start justify-between min-h-[120px]" style={styles.techCard} activeOpacity={0.9} onPress={() => navigation.navigate('EngineSoundDiag')}>
                            <View className="flex-row justify-between items-start w-full mb-3">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center">
                                    <MaterialIcons name="graphic-eq" size={24} color="#0d7ff2" />
                                </View>
                                <MaterialIcons name="arrow-forward" size={20} color="#6b7280" />
                            </View>
                            <View>
                                <Text className="text-lg font-bold text-white mb-1">엔진 소리 진단</Text>
                                <Text className="text-sm font-normal text-gray-400 tracking-wide">AI 엔진음 분석 및 상태 점검</Text>
                            </View>
                        </TouchableOpacity>
                        <TouchableOpacity className="w-full bg-[#ffffff08] border border-[#ffffff14] rounded-2xl p-5 active:bg-white/5 items-start justify-between min-h-[120px]" activeOpacity={0.9} onPress={() => navigation.navigate('Filming')}>
                            <View className="flex-row justify-between items-start w-full mb-3">
                                <View className="h-10 w-10 rounded-lg bg-[#1b2127] border border-white/10 items-center justify-center">
                                    <MaterialIcons name="camera-alt" size={24} color="#0d7ff2" />
                                </View>
                                <MaterialIcons name="arrow-forward" size={20} color="#6b7280" />
                            </View>
                            <View>
                                <Text className="text-lg font-bold text-white mb-1">AI 영상 진단</Text>
                                <Text className="text-sm font-normal text-gray-400 tracking-wide">타이어 마모, 진단 코드 등 시각적 분석</Text>
                            </View>
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
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 4.65,
        elevation: 8,
    }
});
