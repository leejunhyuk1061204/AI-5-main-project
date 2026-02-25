import React, { useEffect, useState } from 'react';
import { View, Text, ActivityIndicator, TouchableOpacity, Linking } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { MaterialIcons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import BaseScreen from '../components/layout/BaseScreen';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useUserStore } from '../store/useUserStore';
import { useAlertStore } from '../store/useAlertStore';

/**
 * 결제 성공 딥링크 전용 화면.
 * 흐름: 카카오 결제 완료 → 백엔드 콜백에서 승인 → frontend://payment/success?order_id=...&status=success 로 리다이렉트 → 이 화면.
 * 백엔드에서 이미 승인·멤버십 반영이 끝났으므로 여기서는 프로필 갱신 + 알림만 처리.
 */
export default function PaymentSuccess() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const showAlert = useAlertStore(state => state.showAlert);
    const [loading, setLoading] = useState(true);
    const [success, setSuccess] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const loadUser = useUserStore(state => state.loadUser);

    useEffect(() => {
        const run = async () => {
            try {
                WebBrowser.maybeCompleteAuthSession();

                const params = (route.params as Record<string, string> | undefined) || {};
                let orderId = params.order_id;
                if (!orderId) {
                    const initialUrl = await Linking.getInitialURL();
                    if (initialUrl) {
                        try {
                            orderId = new URL(initialUrl).searchParams.get('order_id') ?? undefined;
                        } catch {
                            orderId = undefined;
                        }
                    }
                }
                if (!orderId) orderId = await AsyncStorage.getItem('temp_order_id');

                if (!orderId) {
                    setErrorMsg('주문 정보를 찾을 수 없습니다.');
                    setSuccess(false);
                    return;
                }

                await loadUser();
                setSuccess(true);
                await AsyncStorage.removeItem('temp_order_id');
                showAlert('결제 완료', '멤버십이 변경되었습니다.', 'SUCCESS', () => {
                    navigation.reset({ index: 0, routes: [{ name: 'MainPage' }] });
                });
            } catch {
                setErrorMsg('결제 결과를 불러오지 못했습니다.');
                setSuccess(false);
                await loadUser();
            } finally {
                setLoading(false);
            }
        };
        run();
    }, [route.params]);

    const HeaderCustom = (
        <View className="flex-row items-center justify-center py-4 border-b border-white/5">
            <Text className="text-white text-lg font-bold">결제 결과</Text>
        </View>
    );

    return (
        <BaseScreen header={HeaderCustom} padding={true}>
            <View className="flex-1 items-center justify-center p-5">
                {loading ? (
                    <View className="items-center gap-4">
                        <ActivityIndicator size="large" color="#0d7ff2" />
                        <Text className="text-white/70 text-base">결제 승인 중입니다...</Text>
                    </View>
                ) : success ? (
                    <View className="items-center gap-6">
                        <View className="w-20 h-20 rounded-full bg-green-500/20 items-center justify-center">
                            <MaterialIcons name="check" size={40} color="#4ade80" />
                        </View>
                        <View className="items-center gap-2">
                            <Text className="text-white text-2xl font-bold">결제 성공!</Text>
                            <Text className="text-white/60 text-center">
                                프리미엄 멤버십 구독이 시작되었습니다.{'\n'}
                                이제 모든 기능을 무제한으로 이용해보세요.
                            </Text>
                        </View>
                        <TouchableOpacity
                            className="bg-[#0d7ff2] px-8 py-3 rounded-xl mt-4"
                            onPress={() => {
                                navigation.reset({
                                    index: 0,
                                    routes: [{ name: 'MainPage' }],
                                });
                            }}
                        >
                            <Text className="text-white font-bold text-base">확인</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <View className="items-center gap-6">
                        <View className="w-20 h-20 rounded-full bg-red-500/20 items-center justify-center">
                            <MaterialIcons name="error-outline" size={40} color="#ef4444" />
                        </View>
                        <View className="items-center gap-2">
                            <Text className="text-white text-2xl font-bold">결제 실패</Text>
                            <Text className="text-white/60 text-center">{errorMsg}</Text>
                        </View>
                        <TouchableOpacity
                            className="bg-gray-700 px-8 py-3 rounded-xl mt-4"
                            onPress={() => navigation.goBack()}
                        >
                            <Text className="text-white font-bold text-base">돌아가기</Text>
                        </TouchableOpacity>
                    </View>
                )}
            </View>
        </BaseScreen>
    );
}
