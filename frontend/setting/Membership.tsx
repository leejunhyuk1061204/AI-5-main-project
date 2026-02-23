import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Dimensions, Linking } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';

import { LinearGradient } from 'expo-linear-gradient';
import * as WebBrowser from 'expo-web-browser';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAlertStore } from '../store/useAlertStore';
import { useUserStore } from '../store/useUserStore';
import BaseScreen from '../components/layout/BaseScreen';
import paymentApi from '../api/paymentApi';

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
        color: '#0d7ff2',
        gradientColors: ['#0d7ff2', '#0062cc'] as const,
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
        color: '#c5a059',
        gradientColors: ['#c5a059', '#8b6914'] as const,
        recommended: true,
    },
];

export default function Membership() {
    const navigation = useNavigation<any>();
    const showAlert = useAlertStore(state => state.showAlert);
    const { membership: currentLevel, membershipExpiry, loadUser } = useUserStore();
    const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

    // 내부 ID(lower)와 DB 레벨(upper) 매핑
    const currentPlan = currentLevel?.toLowerCase() || 'free';

    // 화면이 포커스될 때마다 사용자 정보 갱신 (결제 후 복귀 시)
    useFocusEffect(
        React.useCallback(() => {
            console.log('Membership page focused - reloading user data');
            loadUser();
        }, [])
    );

    const handleSelectPlan = (planId: string) => {
        if (planId === currentPlan) return;
        setSelectedPlan(planId);
    };

    const handleUpgrade = async () => {
        if (!selectedPlan) return;
        const plan = MEMBERSHIP_PLANS.find(p => p.id === selectedPlan);
        if (!plan) return;

        // 무료 플랜으로 변경 (초기화) 처리
        if (selectedPlan === 'free') {
            showAlert(
                '멤버십 변경',
                '무료 플랜으로 변경하시면 현재 누리고 계신 모든 유능 혜택이 즉시 사라집니다. 정말 변경하시겠습니까?',
                'WARNING',
                async () => {
                    try {
                        await paymentApi.resetMembership();
                        await useUserStore.getState().loadUser(); // Zustand 스토어 데이터 갱신
                        showAlert('성공', '무료 플랜으로 변경되었습니다.', 'SUCCESS', () => {
                            navigation.navigate('MainPage');
                        });
                        setSelectedPlan(null);
                    } catch (error) {
                        console.error('Reset Membership Error:', error);
                        showAlert('오류', '멤버십 변경 중 문제가 발생했습니다.', 'ERROR');
                    }
                },
                { confirmText: '변경 확인', cancelText: '취소', isDestructive: true }
            );
            return;
        }

        try {
            console.log('Initiating payment for:', plan.name);
            const response = await paymentApi.ready(plan.name, plan.priceValue);
            console.log('Payment ready response:', response);

            const urlToOpen = response.next_redirect_mobile_url || response.next_redirect_app_url;
            console.log('URL to open:', urlToOpen);

            if (urlToOpen) {
                await AsyncStorage.setItem('temp_order_id', response.orderId || '');
                console.log('Order ID saved:', response.orderId);

                // 외부 브라우저로 결제 페이지 열기 (카카오톡 앱으로 이동)
                // 결제 완료 후 딥링크로 앱이 자동으로 열림
                await Linking.openURL(urlToOpen);
                console.log('External browser opened');
            }
        } catch (error) {
            console.error('Payment Error:', error);
            showAlert('결제 오류', '결제 준비 중 문제가 발생했습니다.', 'ERROR');
        }
    };

    const currentPlanData = MEMBERSHIP_PLANS.find(p => p.id === currentPlan);

    const HeaderCustom = (
        <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
            <TouchableOpacity
                className="w-10 h-10 items-center justify-center"
                onPress={() => navigation.goBack()}
            >
                <MaterialIcons name="arrow-back-ios-new" size={24} color="#0d7ff2" />
            </TouchableOpacity>
            <Text className="text-white text-lg font-bold flex-1 text-center pr-10">멤버십 관리</Text>
        </View>
    );

    const FooterButton = selectedPlan && selectedPlan !== currentPlan ? (
        <View className="p-5 bg-background-dark">
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
        </View>
    ) : null;

    return (
        <BaseScreen
            header={HeaderCustom}
            footer={FooterButton}
            scrollable={true}
            padding={false}
        >
            <View className="pb-24">
                {/* 현재 멤버십 상태 */}
                <View className="px-5 pt-6 pb-4">
                    <LinearGradient
                        colors={currentPlanData?.gradientColors || ['#374151', '#1f2937']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 1 }}
                        className="p-6 rounded-2xl border border-white/10 relative overflow-hidden"
                    >
                        <View className="absolute -right-10 -top-10 w-32 h-32 bg-white/10 rounded-full" />
                        <View className="absolute -left-5 -bottom-5 w-20 h-20 bg-black/20 rounded-full" />

                        <View className="flex-row items-center gap-2 mb-4">
                            <MaterialIcons name="stars" size={20} color="white" />
                            <Text className="text-white/80 text-sm font-medium uppercase tracking-wider">현재 플랜</Text>
                        </View>

                        <Text className="text-white text-3xl font-bold mb-1">
                            {currentPlanData?.name || (currentLevel === 'BUSINESS' ? 'Business' : currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1))}
                        </Text>
                        <Text className="text-white/70 text-sm">
                            {currentPlan === 'free' ? '무료 플랜 이용 중' : `만료 예정일: ${membershipExpiry ? membershipExpiry.substring(0, 10).replace(/-/g, '.') : '-'}`}
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
                            style={{
                                borderColor: (plan.id === currentPlan || selectedPlan === plan.id) ? plan.color : 'rgba(255,255,255,0.1)',
                                borderWidth: (plan.id === currentPlan || selectedPlan === plan.id) ? 2 : 1,
                                backgroundColor: (plan.id === currentPlan || selectedPlan === plan.id) ? `${plan.color}15` : '#17212b'
                            }}
                            className="mb-4 rounded-2xl overflow-hidden"
                            onPress={() => handleSelectPlan(plan.id)}
                            activeOpacity={0.8}
                        >
                            {plan.recommended && (
                                <View style={{ backgroundColor: plan.id === 'business' ? '#c5a059' : '#0d7ff2' }} className="py-1.5 px-4">
                                    <Text className={`${plan.id === 'business' ? 'text-black' : 'text-white'} text-xs font-bold text-center uppercase tracking-wider`}>
                                        BEST VALUE
                                    </Text>
                                </View>
                            )}

                            <View className="p-5">
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
                                                <MaterialIcons name="check-circle" size={14} color={plan.color} />
                                                <Text style={{ color: plan.color }} className="text-xs font-medium">현재 이용 중</Text>
                                            </View>
                                        )}
                                    </View>
                                    <View className="items-end">
                                        <Text className="text-white text-2xl font-bold">{plan.price}</Text>
                                        {plan.period && (
                                            <Text className="text-gray-500 text-sm">정기결제 {plan.period}</Text>
                                        )}
                                    </View>
                                </View>

                                {/* 체크 + 혜택 설명 주석 처리 */}
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


            </View>
        </BaseScreen>
    );
}
