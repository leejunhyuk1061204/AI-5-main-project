import React, { useEffect, useRef } from 'react';
import { View, Text, Animated, useWindowDimensions } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import Svg, { Path } from 'react-native-svg';
import { MaterialIcons } from '@expo/vector-icons';

export default function SplashScreen({ onFinish }: { onFinish: () => void }) {
    const { width, height } = useWindowDimensions();
    // Base design width (e.g., iPhone 13/14)
    const BASE_WIDTH = 390;
    const scale = width / BASE_WIDTH;

    // Helper to normalize sizes
    const normalize = (size: number) => Math.round(size * scale);

    const fadeAnim = useRef(new Animated.Value(0)).current;
    const slideAnim = useRef(new Animated.Value(20)).current;
    const slowFadeAnim = useRef(new Animated.Value(0)).current;
    const delayedFadeAnim = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        Animated.parallel([
            Animated.timing(fadeAnim, {
                toValue: 1,
                duration: 1500,
                useNativeDriver: false,
            }),
            Animated.timing(slideAnim, {
                toValue: 0,
                duration: 1500,
                useNativeDriver: false,
            }),
            Animated.timing(slowFadeAnim, {
                toValue: 1,
                duration: 2000,
                useNativeDriver: false,
            }),
            Animated.sequence([
                Animated.delay(500),
                Animated.timing(delayedFadeAnim, {
                    toValue: 1,
                    duration: 1500,
                    useNativeDriver: false,
                }),
            ]),
        ]).start(() => {
            setTimeout(() => {
                if (onFinish) onFinish();
            }, 3000);
        });
    }, []);

    // Calculated sizes
    const iconSize = normalize(100);
    const glowSize = normalize(160); // w-40 h-40 is 10rem = 160px
    const titleSize = normalize(36); // text-4xl is ~36px
    const subtitleSize = normalize(12); // text-xs is ~12px
    const spacingBottom = normalize(64); // pb-16
    const spacingMargin = normalize(48); // mb-12

    return (
        <View className="flex-1 bg-deep-black items-center justify-center overflow-hidden">
            <StatusBar style="light" />

            {/* Glow Effects - Scaled relative to screen but kept large */}
            <Animated.View style={{ opacity: slowFadeAnim, width: width * 1.5, height: width * 1.5 }} className="absolute -top-[30%] -left-[20%] bg-primary/10 rounded-full blur-3xl" />
            <Animated.View style={{ opacity: slowFadeAnim, width: width * 1.2, height: width * 1.2 }} className="absolute -bottom-[20%] -right-[10%] bg-primary/5 rounded-full blur-3xl" />

            <View style={{ paddingBottom: spacingBottom }} className="relative z-10 flex-col items-center justify-center w-full px-6 flex-grow">
                <Animated.View
                    style={{
                        opacity: fadeAnim,
                        transform: [{ translateY: slideAnim }],
                        marginBottom: spacingMargin
                    }}
                    className="relative items-center"
                >
                    {/* Central Glow/Blur */}
                    <View style={{ width: glowSize, height: glowSize }} className="absolute bg-primary/20 rounded-full blur-2xl opacity-50" />

                    <View className="items-center justify-center">
                        <View className="relative z-20">
                            <MaterialIcons name="directions-car" size={iconSize} color="#00f0ff" style={{ opacity: 0.9 }} />
                        </View>

                        {/* Waveform SVG */}
                        <View style={{ width: normalize(140), height: normalize(40), marginTop: normalize(-20) }} className="z-10 items-center justify-center opacity-90 overflow-hidden">
                            <Svg height="100%" width="100%" viewBox="0 0 100 24" fill="none">
                                <Path
                                    d="M0 12L10 12L15 4L25 20L35 8L45 16L55 12L65 12L70 18L80 6L90 12L100 12"
                                    stroke="#0d7ff2"
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                />
                            </Svg>
                        </View>
                    </View>
                </Animated.View>

                <Animated.View
                    style={{
                        opacity: fadeAnim,
                        transform: [{ translateY: slideAnim }]
                    }}
                    className="items-center gap-3"
                >
                    <Text style={{ fontSize: titleSize, lineHeight: titleSize * 1.2 }} className="font-semibold tracking-wide text-white text-center">
                        Project TBD
                    </Text>
                    <View style={{ width: normalize(32), height: normalize(1) }} className="bg-primary/50 rounded-full" />
                </Animated.View>
            </View>

            <Animated.View
                style={{
                    opacity: delayedFadeAnim,
                    transform: [{ translateY: slideAnim }],
                    bottom: spacingBottom
                }}
                className="absolute left-0 right-0 items-center z-20 px-8"
            >
                <Text style={{ fontSize: subtitleSize, letterSpacing: subtitleSize * 0.3 }} className="text-blue-100/60 font-light uppercase text-center">
                    AI 기반 예지 정비 시스템
                </Text>
            </Animated.View>

        </View>
    );
}
