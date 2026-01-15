import React, { useEffect } from 'react';
import { View, Text, TouchableOpacity, ImageBackground, Dimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
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

const { width } = Dimensions.get('window');

export default function ActiveLoading({ navigation }: any) {
    const insets = useSafeAreaInsets();

    // Animations
    const scanLineY = useSharedValue(0);
    const particleOpacity = useSharedValue(0.3);
    const rotate = useSharedValue(0);

    useEffect(() => {
        // Scanner Line Animation
        scanLineY.value = withRepeat(
            withTiming(1, { duration: 3000, easing: Easing.linear }),
            -1,
            true
        );

        // Particle Pulse
        particleOpacity.value = withRepeat(
            withSequence(
                withTiming(1, { duration: 800 }),
                withTiming(0.3, { duration: 800 })
            ),
            -1,
            true
        );

        // Slow rotation for decorative ring
        rotate.value = withRepeat(
            withTiming(360, { duration: 20000, easing: Easing.linear }),
            -1,
            false
        );
        // Auto-navigate to success screen after 5 seconds
        const timer = setTimeout(() => {
            navigation.replace('ActiveSuccess');
        }, 5000);

        return () => clearTimeout(timer);
    }, []);

    const animatedScanLineStyle = useAnimatedStyle(() => ({
        top: `${scanLineY.value * 100}%`,
    }));

    const animatedParticleStyle = useAnimatedStyle(() => ({
        opacity: particleOpacity.value,
    }));

    const animatedRotateStyle = useAnimatedStyle(() => ({
        transform: [{ rotate: `${rotate.value}deg` }],
    }));

    // Reusable Status Item
    const StatusItem = ({ icon, label, status, isWaiting = false, isLast = false }: { icon: keyof typeof MaterialIcons.glyphMap, label: string, status: string, isWaiting?: boolean, isLast?: boolean }) => (
        <View className={`flex-1 bg-white/5 border border-white/5 rounded-lg p-3 flex-row items-center gap-3 ${isWaiting ? 'opacity-50' : ''}`}>
            <View className={`w-8 h-8 rounded-full items-center justify-center shrink-0 ${isWaiting ? 'bg-white/5' : 'bg-primary/10'}`}>
                <MaterialIcons
                    name={icon}
                    size={18}
                    color={isWaiting ? '#94a3b8' : '#0d7ff2'}
                />
            </View>
            <View>
                <Text className="text-[10px] uppercase tracking-wider text-slate-400 mb-0.5">{label}</Text>
                <Text className={`text-xs font-bold ${isWaiting ? 'text-slate-400' : 'text-white'}`}>
                    {status}
                </Text>
            </View>
        </View>
    );

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View
                className="z-10 bg-transparent absolute top-0 w-full"
                style={{ paddingTop: insets.top }}
            >
                <View className="flex-row items-center justify-between px-4 py-3">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back" size={24} color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold tracking-tight uppercase opacity-90 pr-10 flex-1 text-center">
                        AI Diagnostics
                    </Text>
                </View>
            </View>

            {/* Main Content */}
            <View className="flex-1 items-center justify-center px-6 pb-8">

                {/* Central Visual: Holographic Car Scanner */}
                <View className="relative w-full aspect-square max-h-[360px] mb-8 items-center justify-center">

                    {/* Background Glow Effect (Simulated with View and shadow) */}
                    <View className="absolute w-[80%] h-[80%] bg-primary/20 rounded-full blur-3xl opacity-30" />

                    {/* Rotating Hexagon Pattern (Decorative Ring) */}
                    <Animated.View
                        style={[
                            animatedRotateStyle,
                            {
                                position: 'absolute', width: '100%', height: '100%',
                                borderRadius: 999, borderWidth: 1, borderColor: 'rgba(13,127,242,0.1)',
                                borderStyle: 'dashed'
                            }
                        ]}
                    />

                    {/* Main Hologram Image */}
                    <View className="w-full h-full relative z-10 overflow-hidden rounded-2xl">
                        <ImageBackground
                            source={{ uri: "https://lh3.googleusercontent.com/aida-public/AB6AXuBrbOpEDKXATHlLHpS3GcTwAzp_yKQDUm98m3S6dgStGdY9E9FbyxKJJEcIqX2JHARPzYLv3bwASRstoXUZTtKfxD7U51lwMEdoIZGgp7pRrPwrPILsPnUWSQ10odw_FXea7qH_wmlGTvVzeVHM7YgChicjH6yEGbfqhaCWuHKe9H-KdUQMZjKtYH1pNsmvPt9VFVsEdSqbS4R9CDAGlskDuKfCc2hhTHJe1Iiv_ztmrHSowk1B7NsidsymB4KRl4PEJcJjokCar12y" }}
                            className="w-full h-full"
                            resizeMode="contain"
                            style={{ opacity: 0.9 }}
                        >
                            {/* Overlay to make it blueish */}
                            <View className="absolute inset-0 bg-[#101922]/40" />
                        </ImageBackground>

                        {/* Scanner Line */}
                        <Animated.View
                            style={[
                                animatedScanLineStyle,
                                {
                                    position: 'absolute', left: 0, right: 0, height: 2,
                                    backgroundColor: '#0d7ff2',
                                    shadowColor: '#0d7ff2', shadowOpacity: 1, shadowRadius: 10, elevation: 5
                                }
                            ]}
                        />

                        {/* Floating Data Points */}
                        <Animated.View style={[animatedParticleStyle, { position: 'absolute', top: '30%', right: '15%', flexDirection: 'row', alignItems: 'center', gap: 4 }]}>
                            <View className="w-1.5 h-1.5 rounded-full bg-primary" />
                            <Text className="text-[10px] text-primary font-mono opacity-80">ENG-01</Text>
                        </Animated.View>
                        <Animated.View style={[animatedParticleStyle, { position: 'absolute', bottom: '25%', left: '15%', flexDirection: 'row', alignItems: 'center', gap: 4 }]}>
                            <View className="w-1.5 h-1.5 rounded-full bg-primary" />
                            <Text className="text-[10px] text-primary font-mono opacity-80">TRS-V2</Text>
                        </Animated.View>
                    </View>
                </View>

                {/* Headline Text */}
                <View className="w-full items-center mb-10">
                    <Text className="text-white text-[26px] font-bold leading-tight mb-2 text-center">
                        차량 데이터를{'\n'}
                        <Text className="text-primary">정밀 분석</Text> 중입니다...
                    </Text>
                    <Text className="text-slate-400 text-sm font-normal leading-relaxed text-center px-4">
                        AI가 차량의 상태를 실시간으로 진단하고{'\n'}잠재적인 위험 요소를 파악합니다.
                    </Text>
                </View>

                {/* Progress Section */}
                <View className="w-full gap-4 mb-5">
                    <View className="flex-row justify-between items-end px-1">
                        <View className="gap-1">
                            <Text className="text-primary text-xs font-bold tracking-widest uppercase">Status</Text>
                            <View className="flex-row items-center gap-2">
                                {/* Simple spin animation replacement just with icon for now or reusable spin */}
                                <MaterialIcons name="sync" size={14} color="#9cabba" className="animate-spin" />
                                <Text className="text-[#9cabba] text-sm font-medium">DTC 고장 코드 스캔 중...</Text>
                            </View>
                        </View>
                        <Text className="text-white text-3xl font-bold tracking-tighter">67%</Text>
                    </View>

                    {/* Progress Bar Container */}
                    <View className="h-1.5 w-full bg-[#2a3848] rounded-full overflow-hidden relative">
                        {/* Fill */}
                        <View className="h-full bg-primary w-[67%] shadow-[0_0_10px_rgba(13,127,242,0.6)]" />
                    </View>
                </View>

                {/* Technical Grid */}
                <View className="w-full flex-row flex-wrap gap-3">
                    <View className="w-full flex-row gap-3">
                        <StatusItem icon="memory" label="ECU System" status="Connecting..." />
                        <StatusItem icon="bolt" label="Battery" status="Voltage Stable" />
                    </View>
                    <View className="w-full flex-row gap-3">
                        <StatusItem icon="settings-suggest" label="Engine" status="Analyzing..." />
                        <StatusItem icon="water-drop" label="Fluids" status="Waiting" isWaiting />
                    </View>
                </View>

            </View>
        </View>
    );
}
