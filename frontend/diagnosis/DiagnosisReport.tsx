import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, BackHandler } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import Header from '../header/Header';
import BaseScreen from '../components/layout/BaseScreen';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { getDiagnosisSessionStatus } from '../api/aiApi';

export default function DiagnosisReport() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    // Store is ONLY used for resetting logic on exit, NOT for data display
    const { reset } = useAiDiagnosisStore();

    const [report, setReport] = useState<any>(route.params?.reportData || null);
    const [loading, setLoading] = useState(false);

    const sessionId = route.params?.sessionId || report?.sessionId;

    useEffect(() => {
        // If we have a sessionId but no full report details (e.g. from notification or partial list), fetch it
        if (sessionId && (!report || !report.finalReport)) {
            fetchReportDetails(sessionId);
        }
    }, [sessionId]);

    const fetchReportDetails = async (id: string) => {
        try {
            setLoading(true);
            const data = await getDiagnosisSessionStatus(id);
            if (data) {
                // API returns various structures, normalize if needed
                const resultData = data.report || data.result || data;
                setReport(resultData);
            }
        } catch (error) {
            console.error("Failed to fetch report details:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleFinish = () => {
        // If this was an active session, clear the global store
        // If it was history viewing, this is harmless
        reset();
        navigation.navigate('DiagTab');
    };

    // 하드웨어 뒤로가기 처리
    useEffect(() => {
        const backHandler = BackHandler.addEventListener(
            'hardwareBackPress',
            () => {
                handleFinish();
                return true; // 기본 동작 방지
            }
        );

        return () => backHandler.remove();
    }, []);

    if (loading || !report) {
        return (
            <BaseScreen header={<Header />} padding={false} useBottomNav={false}>
                <View className="flex-1 items-center justify-center bg-[#101922]">
                    <ActivityIndicator size="large" color="#0d7ff2" className="mb-4" />
                    <Text className="text-white">리포트 데이터를 불러오는 중입니다...</Text>
                </View>
            </BaseScreen>
        );
    }

    return (
        <BaseScreen header={<Header />} padding={false} useBottomNav={false}>
            <View className="flex-1 bg-background-dark">
                <ScrollView
                    className="flex-1 px-6 pt-4"
                    showsVerticalScrollIndicator={false}
                    contentContainerStyle={{ paddingBottom: 40 }}
                >
                    {/* 페이지 타이틀 */}
                    <Text className="text-white text-2xl font-bold mb-4">종합 진단 내역서</Text>

                    {/* 진단 완료 상태 배지 카드 */}
                    <View className="bg-white/5 border border-white/10 rounded-2xl p-5 mb-4">
                        <View className="flex-row items-center gap-1.5 px-3 py-1 rounded-full bg-green-500/10 border border-green-500/20 self-start mb-3">
                            <MaterialIcons name="check-circle" size={12} color="#22c55e" />
                            <Text className="text-xs font-bold text-green-500 uppercase tracking-wider">Completed</Text>
                        </View>
                        <Text className="text-white text-lg font-semibold">진단이 완료되었습니다</Text>
                        <Text className="text-text-muted text-sm mt-1">차량 상태 분석 및 AI 통합 판단 완료</Text>
                    </View>

                    {/* 진단 요약 섹션 */}
                    <View className="bg-white/5 border border-white/10 rounded-2xl p-5 mb-4">
                        <View className="flex-row items-center mb-3">
                            <View className="w-10 h-10 rounded-xl bg-primary/10 items-center justify-center">
                                <MaterialIcons name="summarize" size={20} color="#0d7ff2" />
                            </View>
                            <Text className="text-lg font-bold text-white ml-3">진단 요약</Text>
                        </View>
                        <Text className="text-white/90 text-[15px] leading-7">
                            {report.summary || '차량 상태에 대한 시계열 분석 및 AI 통합 판단이 완료되었습니다.'}
                        </Text>
                    </View>

                    {/* 주요 권장 사항 섹션 */}
                    <View className="bg-white/5 border border-white/10 rounded-2xl p-5 mb-4">
                        <View className="flex-row items-center mb-3">
                            <View className="w-10 h-10 rounded-xl bg-warning/10 items-center justify-center">
                                <MaterialIcons name="warning" size={20} color="#f59e0b" />
                            </View>
                            <Text className="text-lg font-bold text-white ml-3">주요 권장 사항</Text>
                        </View>

                        {report.finalReport || report.description ? (
                            <View className="bg-warning/5 border border-warning/20 rounded-xl p-4">
                                <Text className="text-white/90 text-[15px] leading-7">
                                    {report.finalReport || report.description}
                                </Text>
                            </View>
                        ) : (
                            <View className="bg-surface-card border border-white/10 rounded-xl p-4">
                                <Text className="text-text-muted text-sm text-center">
                                    특별한 조치 사항이 없습니다
                                </Text>
                            </View>
                        )}
                    </View>

                    {/* 하단 액션 버튼 */}
                    <TouchableOpacity
                        className="bg-primary py-4 rounded-xl items-center mt-2 shadow-lg active:bg-primary/90"
                        onPress={handleFinish}
                    >
                        <View className="flex-row items-center gap-2">
                            <Text className="text-white font-bold text-base">진단 세션 종료</Text>
                            <MaterialIcons name="check" size={18} color="#fff" />
                        </View>
                    </TouchableOpacity>
                </ScrollView>
            </View>
        </BaseScreen>
    );
}
