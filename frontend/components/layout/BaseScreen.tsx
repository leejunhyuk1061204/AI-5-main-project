import React from 'react';
import { View, Platform } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { KeyboardAwareScrollView, KeyboardAvoidingView } from 'react-native-keyboard-controller';
import { useUIStore } from '../../store/useUIStore';

interface BaseScreenProps {
    children: React.ReactNode;
    header?: React.ReactNode;
    footer?: React.ReactNode;
    scrollable?: boolean;
    avoidKeyboard?: boolean; // 키보드 회피 활성화 여부
    padding?: boolean;
    useBottomNav?: boolean;
    bgColor?: string;
}

/**
 * 프로젝트 표준 화면 래퍼 (BaseScreen)
 * 1. SafeArea 및 전역 배경색 일괄 적용
 * 2. Keyboard Controller를 이용한 부드러운 키보드 대응 (ScrollView 또는 View 선택 가능)
 * 3. 하단 3중 레이어 여백 자동 확보
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
}: BaseScreenProps) {
    const insets = useSafeAreaInsets();
    const globalBottomNavVisible = useUIStore((state) => state.bottomNavVisible);

    // 실제 여백 확보 여부
    const needsBottomNavSpace = useBottomNav && globalBottomNavVisible;

    // 공통 패딩 스타일
    const paddingStyle = padding ? 'px-6' : '';

    let content;
    if (scrollable) {
        content = (
            <KeyboardAwareScrollView
                className={`flex-1 ${paddingStyle}`}
                contentContainerStyle={{
                    paddingBottom: needsBottomNavSpace ? insets.bottom + 100 : insets.bottom + 20,
                    paddingTop: 10
                }}
                showsVerticalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
                bottomOffset={needsBottomNavSpace ? 80 : 0}
            >
                {children}
            </KeyboardAwareScrollView>
        );
    } else {
        // scrollable이 false일 경우, 자식 요소에서 직접 ScrollView 등을 관리하거나 고정 뷰를 사용할 때
        const viewContent = (
            <View
                className={`flex-1 ${paddingStyle}`}
                style={{
                    paddingBottom: needsBottomNavSpace ? insets.bottom + 80 : insets.bottom
                }}
            >
                {children}
            </View>
        );

        content = avoidKeyboard ? (
            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                className="flex-1"
                keyboardVerticalOffset={0}
            >
                {viewContent}
            </KeyboardAvoidingView>
        ) : viewContent;
    }

    return (
        <View className="flex-1" style={{ backgroundColor: bgColor }}>
            <StatusBar style="light" />
            <SafeAreaView className="flex-1" edges={['top', 'left', 'right']}>
                {/* Header Layer */}
                {header}

                {/* Content Layer */}
                <View className="flex-1">
                    {content}
                </View>

                {/* Footer Layer */}
                {footer}
            </SafeAreaView>
        </View>
    );
}
