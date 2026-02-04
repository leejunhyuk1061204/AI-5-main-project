import React, { useEffect, useState } from 'react';
import { View, Text, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { MaterialIcons } from '@expo/vector-icons';
import BaseScreen from '../components/layout/BaseScreen';
import paymentApi from '../api/paymentApi';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useUserStore } from '../store/useUserStore';

export default function PaymentSuccess() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const [loading, setLoading] = useState(true);
    const [success, setSuccess] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const loadUser = useUserStore(state => state.loadUser);

    useEffect(() => {
        const processPayment = async () => {
            try {
                // URL 파라미터에서 pg_token 추출 (Deep Link로 전달됨)
                const { pg_token, order_id } = route.params || {};

                if (!pg_token) {
                    throw new Error('결제 토큰이 없습니다.');
                }

                // 저장해둔 orderId 가져오기 (URL 파라미터 우선, 없으면 AsyncStorage)
                const orderId = order_id || await AsyncStorage.getItem('temp_order_id');

                if (!orderId) {
                    throw new Error('주문 정보를 찾을 수 없습니다.');
                }

                // 승인 요청
                await paymentApi.approve(pg_token, orderId);

                // 성공 시 사용자 정보 갱신 (등급 등)
                await loadUser();

                setSuccess(true);
                await AsyncStorage.removeItem('temp_order_id'); // cleanup

                // 승인 완료 후 자동으로 홈으로 이동
                navigation.reset({
                    index: 0,
                    routes: [{ name: 'MainPage' }],
                });
            } catch (error: any) {
                console.error('Payment Approve Error:', error);
                setErrorMsg(error.response?.data?.error?.message || error.message || '결제 승인 중 오류가 발생했습니다.');
                setSuccess(false);
            } finally {
                setLoading(false);
            }
        };

        processPayment();
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
