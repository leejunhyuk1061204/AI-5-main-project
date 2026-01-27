import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
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
                    className="flex-1 px-6 pt-6"
                    showsVerticalScrollIndicator={false}
                    contentContainerStyle={{ paddingBottom: 40 }}
                >
                    <Text className="text-white text-2xl font-bold mb-6">종합 진단 내역서</Text>

                    <View className="mb-8">
                        <Text className="text-primary font-bold mb-2 text-lg">진단 요약</Text>
                        <Text className="text-white text-[15px] leading-7">
                            {report.summary || '차량 상태에 대한 시계열 분석 및 AI 통합 판단이 완료되었습니다.'}
                        </Text>
                    </View>

                    <View className="mb-8 border-t border-white/10 pt-6">
                        <Text className="text-warning font-bold mb-2 text-lg">주요 권장 및 조치 사항</Text>
                        <Text className="text-white text-[15px] leading-7">
                            {report.finalReport || report.description || '상세 진단 내용이 없습니다.'}
                        </Text>
                    </View>

                    <TouchableOpacity
                        className="bg-primary py-4 rounded-xl items-center mt-4"
                        onPress={handleFinish}
                    >
                        <Text className="text-white font-bold text-base">진단 세션 종료</Text>
                    </TouchableOpacity>
                </ScrollView>
            </View>
        </BaseScreen>
    );
}
