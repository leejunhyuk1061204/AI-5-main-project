import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, Animated, Dimensions, ImageBackground, StyleSheet } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

export default function Filming() {
    const navigation = useNavigation();
    const insets = useSafeAreaInsets();
    const [permission, requestPermission] = useCameraPermissions();
    const [scanned, setScanned] = useState(false);

    // Animation for scanning line
    const scanAnim = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        // Request camera permission on mount
        if (!permission) {
            requestPermission();
        }

        // Start scanning animation
        Animated.loop(
            Animated.sequence([
                Animated.timing(scanAnim, {
                    toValue: 1,
                    duration: 2500,
                    useNativeDriver: true,
                }),
                Animated.timing(scanAnim, {
                    toValue: 0,
                    duration: 0, // Reset instantly
                    useNativeDriver: true,
                })
            ])
        ).start();
    }, [permission]);

    if (!permission) {
        // Camera permissions are still loading
        return <View className="flex-1 bg-[#050F1A]" />;
    }

    if (!permission.granted) {
        // Camera permissions are not granted yet
        return (
            <View className="flex-1 bg-[#050F1A] items-center justify-center p-6">
                <Text className="text-white text-center mb-4">카메라 권한이 필요합니다.</Text>
                <TouchableOpacity onPress={requestPermission} className="bg-primary px-4 py-2 rounded-lg">
                    <Text className="text-white font-bold">권한 허용</Text>
                </TouchableOpacity>
            </View>
        );
    }

    // Interpolate scan animation for vertical movement
    const translateY = scanAnim.interpolate({
        inputRange: [0, 1],
        outputRange: [-150, 150], // Adjust based on guide size
    });

    return (
        <View className="flex-1 bg-black">
            <StatusBar style="light" />

            {/* Top Bar with safe area top padding */}
            <View
                className="flex-row items-center justify-between px-4 py-2 z-20 absolute top-0 left-0 right-0 bg-transparent"
                style={{ paddingTop: insets.top }}
            >
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <View className="items-center">
                    <Text className="text-white text-lg font-bold">AI 복합 진단</Text>
                </View>
                <TouchableOpacity className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10">
                    <MaterialIcons name="help-outline" size={24} color="white" />
                </TouchableOpacity>
            </View>

            {/* Main Content (Camera View) */}
            <View className="absolute inset-0 z-0 bg-black">
                <CameraView
                    style={StyleSheet.absoluteFill}
                    facing="back"
                >
                    {/* Camera Grid Overlay (Simulated with simple borders for now or SVG) */}
                    <View className="absolute inset-0 opacity-20" pointerEvents="none">
                        {/* We can use simple lines or just leave it clean. Let's add the corners. */}
                    </View>

                    {/* Corner Reticles */}
                    <View className="absolute top-32 left-8 w-8 h-8 border-t-2 border-l-2 border-[#0d7ff2]/60 rounded-tl-lg" />
                    <View className="absolute top-32 right-8 w-8 h-8 border-t-2 border-r-2 border-[#0d7ff2]/60 rounded-tr-lg" />
                    <View className="absolute bottom-40 left-8 w-8 h-8 border-b-2 border-l-2 border-[#0d7ff2]/60 rounded-bl-lg" />
                    <View className="absolute bottom-40 right-8 w-8 h-8 border-b-2 border-r-2 border-[#0d7ff2]/60 rounded-br-lg" />

                    {/* Central Guide (Tire Scan) */}
                    <View className="absolute inset-0 items-center justify-center pointer-events-none">
                        <View className="w-[80%] aspect-square max-w-[320px] rounded-full border-2 border-dashed border-[#0d7ff2]/70 items-center justify-center relative shadow-[0_0_30px_rgba(13,127,242,0.2)]">
                            {/* Inner Hub Guide */}
                            <View className="w-[40%] aspect-square rounded-full border border-[#0d7ff2]/30" />

                            {/* Scanning Laser Line */}
                            <Animated.View
                                className="absolute w-full h-[2px] bg-[#0d7ff2] shadow-[0_0_10px_#0d7ff2]"
                                style={{ transform: [{ translateY }] }}
                            />

                            {/* Floating Label */}
                            <View className="absolute -top-10 bg-[#0d7ff2]/20 border border-[#0d7ff2]/40 px-3 py-1 rounded-full flex-row items-center gap-1.5 backdrop-blur-md">
                                <MaterialIcons name="build" size={14} color="#0d7ff2" />
                                <Text className="text-[#0d7ff2] text-xs font-bold tracking-widest uppercase">TIRE SCAN</Text>
                            </View>
                        </View>
                    </View>

                    {/* Instruction Text */}
                    <View className="absolute bottom-40 w-full px-6 items-center justify-center pointer-events-none">
                        <View className="bg-black/60 px-6 py-3 rounded-xl items-center border border-white/10 backdrop-blur-md">
                            <Text className="text-white font-medium text-base mb-0.5">가이드라인에 맞춰 부품을 촬영해 주세요</Text>
                            <Text className="text-slate-300 text-xs">어두운 곳에서는 플래시를 켜주세요</Text>
                        </View>
                    </View>
                </CameraView>
            </View>

            {/* Bottom Controls Area */}
            <View
                className="absolute bottom-0 left-0 right-0 bg-[#050F1A]/80 backdrop-blur-md pt-6 rounded-t-3xl border-t border-white/5 z-20"
                style={{ paddingBottom: insets.bottom + 20 }}
            >
                <View className="flex-row items-center justify-between max-w-sm mx-auto w-full px-6">
                    {/* Flash Button */}
                    <TouchableOpacity className="items-center gap-1">
                        <View className="w-12 h-12 rounded-full bg-[#101922] border border-white/10 items-center justify-center active:bg-white/10">
                            <MaterialIcons name="flash-on" size={20} color="white" />
                        </View>
                        <Text className="text-[10px] text-slate-400 font-medium">플래시</Text>
                    </TouchableOpacity>

                    {/* Shutter Button */}
                    <TouchableOpacity className="relative w-20 h-20 items-center justify-center active:scale-95 transition-all">
                        <LinearGradient
                            colors={['#0d7ff2', '#2563eb']}
                            className="w-16 h-16 rounded-full shadow-lg border-2 border-white/20 z-10"
                        />
                        <View className="absolute w-full h-full rounded-full border-4 border-white/10" />
                        <View className="absolute w-full h-full rounded-full bg-primary/20 blur-lg" />
                    </TouchableOpacity>

                    {/* Switch Mode/Camera */}
                    <TouchableOpacity className="items-center gap-1">
                        <View className="w-12 h-12 rounded-full bg-[#101922] border border-white/10 items-center justify-center active:bg-white/10">
                            <MaterialIcons name="flip-camera-ios" size={20} color="white" />
                        </View>
                        <Text className="text-[10px] text-slate-400 font-medium">전환</Text>
                    </TouchableOpacity>
                </View>
            </View>
        </View>
    );
}
