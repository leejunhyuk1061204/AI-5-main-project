import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';

const { width } = Dimensions.get('window');

// 멤버십 플랜 정의
const MEMBERSHIP_PLANS = [
    {
        id: 'free',
        name: 'Free',
        price: '무료',
        priceValue: 0,
        features: [
            '기본 차량 진단',
            '주행 기록 조회 (7일)',
            '소모품 알림 (월 1회)',
        ],
        color: '#6b7280',
        gradientColors: ['#374151', '#1f2937'] as const,
    },
    {
        id: 'premium',
        name: 'Premium',
        price: '₩9,900',
        priceValue: 9900,
        period: '/월',
        features: [
            'AI 실시간 진단 무제한',
            '주행 기록 전체 조회',
            '소모품 예측 분석',
            'OBD 실시간 모니터링',
            '우선 고객 지원',
        ],
        color: '#c5a059',
        gradientColors: ['#c5a059', '#8b6914'] as const,
        recommended: true,
    },
    {
        id: 'business',
        name: 'Business',
        price: '₩29,900',
        priceValue: 29900,
        period: '/월',
        features: [
            'Premium 전체 기능',
            '다중 차량 관리 (최대 10대)',
            '정비소 연동 서비스',
            'API 접근 권한',
            '전담 매니저 배정',
        ],
        color: '#0d7ff2',
        gradientColors: ['#0d7ff2', '#0062cc'] as const,
    },
];

export default function Membership() {
    const navigation = useNavigation<any>();
    const [currentPlan, setCurrentPlan] = useState('premium');
    const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

    useEffect(() => {
        // 현재 멤버십 상태 불러오기 (mock)
        loadMembershipStatus();
    }, []);

    const loadMembershipStatus = async () => {
        // 실제로는 백엔드에서 조회
        const stored = await AsyncStorage.getItem('membershipPlan');
        if (stored) {
            setCurrentPlan(stored);
        }
    };

    const handleSelectPlan = (planId: string) => {
        if (planId === currentPlan) return;
        setSelectedPlan(planId);
    };

    const handleUpgrade = () => {
        // 실제로는 결제 플로우로 이동
        console.log('Upgrading to:', selectedPlan);
        // navigation.navigate('Payment', { planId: selectedPlan });
    };

    const currentPlanData = MEMBERSHIP_PLANS.find(p => p.id === currentPlan);

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <SafeAreaView className="z-10 bg-background-dark/90 border-b border-white/5" edges={['top']}>
                <View className="flex-row items-center justify-between px-4 py-3">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="#0d7ff2" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold flex-1 text-center pr-10">멤버십 관리</Text>
                </View>
            </SafeAreaView>

            <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
                {/* 현재 멤버십 상태 */}
                <View className="px-5 pt-6 pb-4">
                    <LinearGradient
                        colors={currentPlanData?.gradientColors || ['#374151', '#1f2937']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 1 }}
                        className="p-6 rounded-2xl border border-white/10 relative overflow-hidden"
                    >
                        {/* 배경 효과 */}
                        <View className="absolute -right-10 -top-10 w-32 h-32 bg-white/10 rounded-full" />
                        <View className="absolute -left-5 -bottom-5 w-20 h-20 bg-black/20 rounded-full" />

                        <View className="flex-row items-center gap-2 mb-4">
                            <MaterialIcons name="stars" size={20} color="white" />
                            <Text className="text-white/80 text-sm font-medium uppercase tracking-wider">현재 플랜</Text>
                        </View>

                        <Text className="text-white text-3xl font-bold mb-1">
                            {currentPlanData?.name}
                        </Text>
                        <Text className="text-white/70 text-sm">
                            {currentPlan === 'free' ? '무료 플랜 이용 중' : '다음 결제일: 2026.02.21'}
                        </Text>

                        {currentPlan !== 'free' && (
                            <View className="mt-4 pt-4 border-t border-white/20">
                                <View className="flex-row justify-between">
                                    <Text className="text-white/60 text-sm">월 이용료</Text>
                                    <Text className="text-white font-bold">{currentPlanData?.price}</Text>
                                </View>
                            </View>
                        )}
                    </LinearGradient>
                </View>

                {/* 플랜 선택 */}
                <View className="px-5 pt-4">
                    <Text className="text-gray-500 text-xs font-bold uppercase tracking-[0.15em] mb-4">플랜 비교</Text>

                    {MEMBERSHIP_PLANS.map((plan) => (
                        <TouchableOpacity
                            key={plan.id}
                            className={`mb-4 rounded-2xl border overflow-hidden ${plan.id === currentPlan
                                    ? 'border-2 border-primary bg-primary/5'
                                    : selectedPlan === plan.id
                                        ? 'border-2 border-white/30 bg-white/5'
                                        : 'border-white/10 bg-[#17212b]'
                                }`}
                            onPress={() => handleSelectPlan(plan.id)}
                            activeOpacity={0.8}
                        >
                            {/* 추천 배지 */}
                            {plan.recommended && (
                                <View className="bg-[#c5a059] py-1.5 px-4">
                                    <Text className="text-black text-xs font-bold text-center uppercase tracking-wider">
                                        MOST POPULAR
                                    </Text>
                                </View>
                            )}

                            <View className="p-5">
                                {/* 플랜 헤더 */}
                                <View className="flex-row justify-between items-start mb-4">
                                    <View>
                                        <View className="flex-row items-center gap-2 mb-1">
                                            <View
                                                className="w-3 h-3 rounded-full"
                                                style={{ backgroundColor: plan.color }}
                                            />
                                            <Text className="text-white text-xl font-bold">{plan.name}</Text>
                                        </View>
                                        {plan.id === currentPlan && (
                                            <View className="flex-row items-center gap-1 mt-1">
                                                <MaterialIcons name="check-circle" size={14} color="#0d7ff2" />
                                                <Text className="text-primary text-xs font-medium">현재 이용 중</Text>
                                            </View>
                                        )}
                                    </View>
                                    <View className="items-end">
                                        <Text className="text-white text-2xl font-bold">{plan.price}</Text>
                                        {plan.period && (
                                            <Text className="text-gray-500 text-sm">{plan.period}</Text>
                                        )}
                                    </View>
                                </View>

                                {/* 기능 목록 */}
                                <View className="gap-2.5">
                                    {plan.features.map((feature, index) => (
                                        <View key={index} className="flex-row items-center gap-3">
                                            <View
                                                className="w-5 h-5 rounded-full items-center justify-center"
                                                style={{ backgroundColor: `${plan.color}20` }}
                                            >
                                                <MaterialIcons
                                                    name="check"
                                                    size={12}
                                                    color={plan.color}
                                                />
                                            </View>
                                            <Text className="text-gray-300 text-sm flex-1">{feature}</Text>
                                        </View>
                                    ))}
                                </View>
                            </View>
                        </TouchableOpacity>
                    ))}
                </View>

                {/* 혜택 안내 */}
                <View className="px-5 pt-4">
                    <View className="bg-[#1a2a3a] rounded-2xl p-5 border border-white/5">
                        <View className="flex-row items-center gap-2 mb-3">
                            <MaterialIcons name="auto-awesome" size={18} color="#c5a059" />
                            <Text className="text-[#c5a059] font-bold">프리미엄 혜택</Text>
                        </View>
                        <Text className="text-gray-400 text-sm leading-relaxed">
                            프리미엄 멤버십 가입 시 AI 기반 실시간 차량 진단, 맞춤형 정비 예측, OBD 연동 모니터링 등
                            모든 기능을 무제한으로 이용하실 수 있습니다.
                        </Text>
                    </View>
                </View>
            </ScrollView>

            {/* 하단 버튼 */}
            {selectedPlan && selectedPlan !== currentPlan && (
                <View className="absolute bottom-0 left-0 right-0 p-5 bg-background-dark/95 border-t border-white/10">
                    <SafeAreaView edges={['bottom']}>
                        <TouchableOpacity
                            onPress={handleUpgrade}
                            activeOpacity={0.9}
                        >
                            <LinearGradient
                                colors={MEMBERSHIP_PLANS.find(p => p.id === selectedPlan)?.gradientColors || ['#0d7ff2', '#0062cc']}
                                start={{ x: 0, y: 0 }}
                                end={{ x: 1, y: 0 }}
                                className="py-4 rounded-xl items-center justify-center"
                            >
                                <Text className="text-white font-bold text-lg">
                                    {MEMBERSHIP_PLANS.find(p => p.id === selectedPlan)?.name} 플랜으로 변경
                                </Text>
                            </LinearGradient>
                        </TouchableOpacity>
                    </SafeAreaView>
                </View>
            )}
        </View>
    );
}
