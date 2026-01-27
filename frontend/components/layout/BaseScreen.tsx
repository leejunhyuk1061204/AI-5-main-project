import React from 'react';
import { View, Platform } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { KeyboardAwareScrollView, KeyboardAvoidingView, useKeyboardHandler } from 'react-native-keyboard-controller';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { useUIStore } from '../../store/useUIStore';

// UI 상수 정의
const TAB_BAR_HEIGHT = 64; // Docked 하단바 높이
const FOOTER_MIN_HEIGHT = 60;
const DEFAULT_PADDING = 20;

interface BaseScreenProps {
    children: React.ReactNode;
    header?: React.ReactNode;
    footer?: React.ReactNode;
    scrollable?: boolean;
    avoidKeyboard?: boolean;
    padding?: boolean;
    useBottomNav?: boolean;
    bgColor?: string;
    androidKeyboardBehavior?: 'padding' | 'height' | 'position';
}

/**
 * 프로젝트 표준 화면 래퍼 (BaseScreen)
 * 1. SafeArea 및 전역 배경색 일괄 적용
 * 2. 통합 KeyboardAvoidingView를 통한 자연스러운 화면 축소 (Resize)
 * 3. 기기별 하단 여백 자동 확보 및 하드코딩 제거
 */
export default function BaseScreen({
    children,
    header,
    footer,
    scrollable = true,
    avoidKeyboard = true,
    padding = true,
    useBottomNav = false,
    bgColor = '#101922',
    androidKeyboardBehavior = 'height', // 안드로이드는 height 리사이징이 기본
}: BaseScreenProps) {
    const insets = useSafeAreaInsets();
    const { bottomNavVisible, isKeyboardVisible } = useUIStore();

    // 하단바 영역 확보 여부
    const showBottomNav = useBottomNav && bottomNavVisible;

    // Reanimated: 키보드 높이를 네이티브 스레드에서 추적
    const keyboardHeight = useSharedValue(0);
    const bottomNavHeight = useSharedValue(useBottomNav && bottomNavVisible ? TAB_BAR_HEIGHT + insets.bottom : 0);

    // showBottomNav 변경 시 애니메이션 동기화
    React.useEffect(() => {
        if (showBottomNav) {
            bottomNavHeight.value = withTiming(TAB_BAR_HEIGHT + insets.bottom, { duration: 150 });
        } else {
            // 사라질 때는 애니메이션 없이 즉시(0ms) 제거하여 반응속도 극대화
            bottomNavHeight.value = 0;
        }
    }, [showBottomNav, insets.bottom]);

    useKeyboardHandler({
        onStart: (e) => {
            'worklet';
            keyboardHeight.value = e.height;
            // 키보드가 올라오기 시작하면 하단바 영역을 즉시 0으로 만듦
            if (e.height > 0) {
                bottomNavHeight.value = 0;
            }
        },
        onEnd: (e) => {
            'worklet';
            if (e.height === 0) {
                // 키보드가 완전히 내려갔을 때 확실하게 하단바 영역 복수
                bottomNavHeight.value = withTiming(TAB_BAR_HEIGHT + insets.bottom, { duration: 150 });
            }
        }
    }, [showBottomNav, insets.bottom]);

    const animatedBottomNavStyle = useAnimatedStyle(() => ({
        height: bottomNavHeight.value,
        opacity: bottomNavHeight.value > 0 ? 1 : 0
    }));

    // 키보드 높이만큼 직접 공간을 만드는 스타일
    const animatedKeyboardStyle = useAnimatedStyle(() => ({
        height: keyboardHeight.value,
    }));

    // 공통 패딩 스타일
    const paddingStyle = padding ? 'px-6' : '';

    let content;
    if (scrollable) {
        // 스크롤 가능한 화면: KeyboardAwareScrollView 사용
        content = (
            <KeyboardAwareScrollView
                className={`flex-1 ${paddingStyle}`}
                contentContainerStyle={{
                    paddingBottom: DEFAULT_PADDING,
                    paddingTop: 10
                }}
                showsVerticalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
                // KeyboardAwareScrollView 자체 회피 로직 활용
                bottomOffset={0}
            >
                {children}
            </KeyboardAwareScrollView>
        );
    } else {
        // 고정 화면 (예: 채팅): View 사용
        content = (
            <View className={`flex-1 ${paddingStyle}`}>
                {children}
            </View>
        );
    }

    // 메인 레이아웃 (Header + Content + Footer)
    const mainLayout = (
        <View style={{ flex: 1 }}>
            {/* Header Layer */}
            {header}

            {/* Content Layer (Flex 1) */}
            <View className="flex-1">
                {content}
            </View>

            {/* Footer Layer (채팅 입력창 등) */}
            {footer && (
                <View className="w-full">
                    {footer}
                </View>
            )}
        </View>
    );

    return (
        <View className="flex-1" style={{ backgroundColor: bgColor }}>
            <StatusBar style="light" />
            <SafeAreaView className="flex-1" edges={['top', 'left', 'right', 'bottom']}>
                {avoidKeyboard ? (
                    <KeyboardAvoidingView
                        behavior="padding"
                        style={{ flex: 1 }}
                    >
                        {mainLayout}
                    </KeyboardAvoidingView>
                ) : (
                    mainLayout
                )}
            </SafeAreaView>
        </View>
    );
}
