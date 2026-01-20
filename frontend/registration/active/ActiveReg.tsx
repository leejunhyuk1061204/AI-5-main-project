import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ImageBackground } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { CommonActions } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withRepeat,
    withTiming,
    withSequence,
    Easing
} from 'react-native-reanimated';

import ObdConnect from '../../setting/ObdConnect';

export default function ActiveReg({ navigation }: any) {
    const insets = useSafeAreaInsets();
    const [obdModalVisible, setObdModalVisible] = useState(false);

    // Animations
    const pulseScale = useSharedValue(1);
    const pulseOpacity = useSharedValue(0.5);
    const radarScale = useSharedValue(0.8);
    const radarOpacity = useSharedValue(0.5);

    useEffect(() => {
        // OBD Port Pulse
        pulseScale.value = withRepeat(
            withSequence(
                withTiming(1.5, { duration: 1000 }),
                withTiming(1, { duration: 1000 })
            ),
            -1,
            true
        );
        pulseOpacity.value = withRepeat(
            withSequence(
                withTiming(0, { duration: 1000 }),
                withTiming(0.5, { duration: 1000 })
            ),
            -1,
            true
        );

        // Radar Animation
        radarScale.value = withRepeat(
            withTiming(2, { duration: 2000, easing: Easing.out(Easing.ease) }),
            -1,
            false
        );
        radarOpacity.value = withRepeat(
            withTiming(0, { duration: 2000, easing: Easing.out(Easing.ease) }),
            -1,
            false
        );
    }, []);

    const animatedPulseStyle = useAnimatedStyle(() => ({
        transform: [{ scale: pulseScale.value }],
        opacity: pulseOpacity.value,
    }));

    const animatedRadarStyle = useAnimatedStyle(() => ({
        transform: [{ scale: radarScale.value }],
        opacity: radarOpacity.value,
    }));

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            <View
                className="bg-background-dark/80 backdrop-blur-md z-50 sticky top-0"
                style={{ paddingTop: insets.top }}
            >
                <View className="flex-row items-center justify-between px-4 py-3 pb-4">
                    <TouchableOpacity
                        className="w-12 h-12 items-center justify-center rounded-full hover:bg-slate-800"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} className="text-white" color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold flex-1 text-center pr-12">
                        OBD-II 어댑터 연결
                    </Text>
                </View>
            </View>

            <ScrollView
                className="flex-1 px-5"
                contentContainerStyle={{ paddingBottom: 100 }}
                showsVerticalScrollIndicator={false}
            >
                {/* Main Visual Section */}
                <View className="flex-col w-full py-6 items-center justify-center relative overflow-hidden">
                    <View className="relative w-full max-w-[340px] aspect-[4/3] rounded-2xl bg-slate-900/50 border border-slate-700/50 flex items-center justify-center overflow-hidden shadow-2xl">
                        {/* Tech Grid Background (Simplified with CSS-like overlay) */}
                        <View className="absolute inset-0 opacity-[0.1] bg-[#0d7ff2]/5" />

                        {/* Background Image */}
                        <ImageBackground
                            source={{ uri: "https://lh3.googleusercontent.com/aida-public/AB6AXuApLKE-PnY2Ivst0WmHBQevbVixQJ_ZwzEyVCEw0hvPJYGGdNpKxRQ2EOz0HiKXRNTGCcfjxmiE700CJ4kkcO2IMc5mtOUaRyO_avKqCxmzMB-mHDf97cNhme6XrToNiJD7vTkXP5t7qt4jjkg1y2xohZFompRVwmZAAOjphamO-DgsrBYNTzWtomsEkCPeRsYqi9s5NqX4PC--X45e-M9hYmq7xRTzkYYA6_i5DW7vRpeJkrtmP0yDX9pxvo4a_2DHVBLnZ2Zjkt0r" }}
                            className="w-[85%] h-[85%] absolute z-10 opacity-90"
                            resizeMode="contain"
                        />

                        {/* Animated Port Indicator */}
                        {/* Animated Port Indicator - Corrected Structure */}
                        <View className="absolute bottom-[28%] left-[28%] z-20">
                            {/* 1. Diagonal Line (Up-Right) */}
                            {/* Rotated -45deg around center. Width 40. Center offset calc:
                                X shift: 20 - 20cos(45) = 5.86
                                Y shift: 20sin(45) = 14.14
                                To make visuals start at 0,0: left: -6, top: -14 */}
                            <View
                                className="absolute h-[1.5px] bg-[#0d7ff2]"
                                style={{
                                    width: 40,
                                    left: -6,
                                    top: -14,
                                    transform: [{ rotate: '-45deg' }]
                                }}
                            />

                            {/* 2. Label at End of Line */}
                            <View className="absolute left-[16px] -top-[50px] bg-[#0d1926]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#0d7ff2]/50 shadow-lg">
                                <Text className="text-[11px] font-bold text-[#0d7ff2] tracking-wide">OBD Port</Text>
                            </View>

                            {/* 3. Dot & Pulse at Anchor Point (Rendered Last to be on Top) */}
                            <View className="absolute top-0 left-0 items-center justify-center -ml-[6px] -mt-[6px]">
                                <Animated.View style={[animatedPulseStyle, { width: 30, height: 30, borderRadius: 15, backgroundColor: 'rgba(13, 127, 242, 0.3)', position: 'absolute' }]} />
                                <View className="w-3 h-3 bg-[#0d7ff2] rounded-full shadow-[0_0_10px_#0d7ff2]" />
                            </View>
                        </View>
                    </View>

                    <Text className="text-xs text-slate-400 mt-4 font-medium tracking-wide uppercase opacity-80">
                        일반적인 포트 위치: 운전석 하단
                    </Text>
                </View>

                {/* Step-by-Step Instructions */}
                <View className="flex-1 pt-2 pb-6">
                    <View className="flex-1">

                        {/* Step 1 */}
                        <View className="flex-row gap-4">
                            <View className="items-center">
                                <View className="w-8 h-8 rounded-full bg-primary/20 items-center justify-center border border-primary/20">
                                    <MaterialIcons name="vpn-key" size={18} color="#0d7ff2" />
                                </View>
                                <View className="w-[2px] flex-1 bg-slate-700 min-h-[40px] my-1" />
                            </View>
                            <View className="flex-1 pb-8 pt-1">
                                <Text className="text-white text-base font-bold mb-1">차량 시동을 켜세요</Text>
                                <Text className="text-slate-400 text-sm">안전을 위해 기어를 P단에 놓고 시동을 걸어주세요.</Text>
                            </View>
                        </View>

                        {/* Step 2 */}
                        <View className="flex-row gap-4">
                            <View className="items-center">
                                <View className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center border border-slate-700">
                                    <MaterialIcons name="settings-input-hdmi" size={18} color="#cbd5e1" />
                                </View>
                                <View className="w-[2px] flex-1 bg-slate-700 min-h-[40px] my-1" />
                            </View>
                            <View className="flex-1 pb-8 pt-1">
                                <Text className="text-white text-base font-bold mb-1">어댑터를 OBD 단자에 꽂으세요</Text>
                                <Text className="text-slate-400 text-sm">어댑터의 LED가 켜지는지 확인하세요.</Text>
                            </View>
                        </View>

                        {/* Step 3 */}
                        <View className="flex-row gap-4">
                            <View className="items-center">
                                <View className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center border border-slate-700">
                                    <MaterialIcons name="bluetooth" size={18} color="#cbd5e1" />
                                </View>
                            </View>
                            <View className="flex-1 pb-4 pt-1">
                                <Text className="text-white text-base font-bold mb-1">아래 버튼을 눌러 블루투스로 연결하세요</Text>
                                <Text className="text-slate-400 text-sm">앱이 자동으로 근처의 장치를 찾습니다.</Text>
                            </View>
                        </View>

                    </View>
                </View>

            </ScrollView>

            {/* Bottom Action Button */}
            <View
                className="absolute bottom-0 w-full bg-background-dark/90 p-4 border-t border-slate-800 backdrop-blur-md"
                style={{ paddingBottom: insets.bottom + 16 }}
            >
                <TouchableOpacity
                    className="w-full h-14"
                    activeOpacity={0.9}
                    onPress={() => setObdModalVisible(true)}
                >
                    <LinearGradient
                        colors={['#0d7ff2', '#3b82f6', '#06b6d4']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        className="w-full h-full flex-row items-center justify-center gap-2"
                        style={{ borderRadius: 100 }}
                    >
                        {/* Radar Icon Simulation */}
                        <View className="relative items-center justify-center w-6 h-6 mr-2">
                            <Animated.View
                                style={[
                                    animatedRadarStyle,
                                    {
                                        position: 'absolute',
                                        width: '100%',
                                        height: '100%',
                                        borderRadius: 999,
                                        borderWidth: 2,
                                        borderColor: 'white'
                                    }
                                ]}
                            />
                            <MaterialIcons name="radar" size={24} color="white" />
                        </View>
                        <Text className="text-white text-base font-bold tracking-wide">장치 검색 및 연결</Text>
                    </LinearGradient>
                </TouchableOpacity>
            </View>

            <ObdConnect
                visible={obdModalVisible}
                onClose={() => setObdModalVisible(false)}
                onConnected={(device) => {
                    console.log('Connected during registration:', device.name);
                    setObdModalVisible(false);
                    // Add a small delay for better UX before transitioning
                    setTimeout(() => {
                        navigation.navigate('ActiveLoading');
                    }, 500);
                }}
            />

        </View>
    );
}
