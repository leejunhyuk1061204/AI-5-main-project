import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Image, Dimensions } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAiDiagnosisStore, DiagType } from '../store/useAiDiagnosisStore';
import { getDiagnosisSessionStatus } from '../api/aiApi';
import Header from '../header/Header';

const { width } = Dimensions.get('window');

export default function DiagnosisReport() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const insets = useSafeAreaInsets();
    const { reset } = useAiDiagnosisStore();

    const [report, setReport] = useState<any>(route.params?.reportData || null);
    const [loading, setLoading] = useState(false);

    const sessionId = route.params?.sessionId || report?.sessionId;
    const diagType: DiagType = route.params?.diagType || 'OBD';

    useEffect(() => {
        if (sessionId && (!report || !report.summary)) {
            fetchReportDetails(sessionId);
        }
    }, [sessionId]);

    const fetchReportDetails = async (id: string) => {
        try {
            setLoading(true);
            const data = await getDiagnosisSessionStatus(id);
            if (data) {
                const resultData = data.report || data.result || data;
                setReport(resultData);
            }
        } catch (error) {
            console.error("Failed to fetch report details:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleBack = () => {
        if (route.params?.fromHistory) {
            navigation.goBack();
        } else {
            handleFinish();
        }
    };

    const handleFinish = () => {
        if (route.params?.fromHistory) {
            navigation.goBack();
        } else {
            reset(diagType);
            navigation.navigate('MainPage');
        }
    };

    if (loading) {
        return (
            <View className="flex-1 bg-background-dark items-center justify-center">
                <ActivityIndicator size="large" color="#0d7ff2" />
                <Text className="text-text-dim mt-4">분석 리포트를 불러오는 중입니다...</Text>
            </View>
        );
    }

    if (!report) {
        return (
            <View className="flex-1 bg-background-dark items-center justify-center">
                <MaterialIcons name="error-outline" size={48} color="#64748b" />
                <Text className="text-text-dim mt-4 mb-6">리포트 정보를 찾을 수 없습니다.</Text>
                <TouchableOpacity onPress={handleFinish} className="bg-surface-card px-6 py-3 rounded-xl border border-white/5">
                    <Text className="text-white font-bold">돌아가기</Text>
                </TouchableOpacity>
            </View>
        );
    }

    const reportData = report.report_data || report.reportData || {};
    const riskLevel = report.riskLevel || 'NORMAL';
    const confidenceScore = report.confidence_score || report.confidenceScore || 0;
    const suspectedCauses = reportData.suspected_causes || [];
    const finalGuide = reportData.final_guide || report.finalReport || report.description || '특이사항이 발견되지 않았습니다.';
    const triggerType = report.triggerType || '종합 진단';

    const confidencePercent = Math.round(confidenceScore * 100);

    const getRiskInfo = (level: string) => {
        switch (level) {
            case 'DANGER': return { color: '#ef4444', label: '위험', icon: 'warning', bg: 'bg-error/10', border: 'border-error/30' };
            case 'WARNING': return { color: '#f59e0b', label: '주의', icon: 'error-outline', bg: 'bg-warning/10', border: 'border-warning/30' };
            default: return { color: '#10b981', label: '정상', icon: 'check-circle', bg: 'bg-success/10', border: 'border-success/30' };
        }
    };
    const riskInfo = getRiskInfo(riskLevel);

    const getRiskSummary = (level: string) => {
        switch (level) {
            case 'DANGER': return '차량 상태 위험 감지';
            case 'WARNING': return '차량 점검 필요';
            default: return '차량 상태 정상';
        }
    };
    const riskSummary = getRiskSummary(riskLevel);

    return (
        <View className="flex-1 bg-background-dark">
            {/* 1. Large Header with Vehicle Image (45% Height) */}
            <View className="absolute top-0 w-full h-[45%] z-0">
                <Image
                    source={{ uri: "https://lh3.googleusercontent.com/aida-public/AB6AXuBrbOpEDKXATHlLHpS3GcTwAzp_yKQDUm98m3S6dgStGdY9E9FbyxKJJEcIqX2JHARPzYLv3bwASRstoXUZTtKfxD7U51lwMEdoIZGgp7pRrPwrPILsPnUWSQ10odw_FXea7qH_wmlGTvVzeVHM7YgChicjH6yEGbfqhaCWuHKe9H-KdUQMZjKtYH1pNsmvPt9VFVsEdSqbS4R9CDAGlskDuKfCc2hhTHJe1Iiv_ztmrHSowk1B7NsidsymB4KRl4PEJcJjokCar12y" }}
                    className="w-full h-full opacity-60"
                    resizeMode="cover"
                />
                <LinearGradient
                    colors={['rgba(16, 25, 34, 0.1)', 'rgba(16, 25, 34, 0.8)', '#101922']}
                    locations={[0, 0.7, 1]}
                    className="absolute inset-x-0 bottom-0 h-full"
                />
            </View>

            <ScrollView
                className="flex-1 z-10"
                showsVerticalScrollIndicator={false}
                contentContainerStyle={{ paddingTop: '55%', paddingBottom: 240 }}
            >
                <View className="px-5">
                    {/* 2. Main Title Only (No Icon) */}
                    <View className="items-center mb-16">
                        {/* Title & Summary - Large and Clean */}
                        <Text className="text-white text-3xl font-bold text-center mb-2 drop-shadow-md">
                            {riskSummary}
                        </Text>
                        <Text className="text-text-dim text-xs text-center">
                            {report.createdAt ? new Date(report.createdAt).toLocaleDateString() : new Date().toLocaleDateString()} 진단 완료
                        </Text>
                    </View>

                    {/* 3. Stats Row (Full Width) */}
                    <View className="flex-row gap-3 mb-6 h-24">
                        <View className="flex-1 bg-surface-card border border-white/10 rounded-2xl p-4 justify-between relative overflow-hidden">
                            <LinearGradient colors={['rgba(13, 127, 242, 0.1)', 'transparent']} className="absolute inset-0" />
                            <Text className="text-text-dim text-xs font-medium">AI 신뢰도 분석</Text>
                            <View>
                                <View className="flex-row items-baseline gap-1">
                                    <Text className="text-primary text-3xl font-bold">{confidencePercent}</Text>
                                    <Text className="text-primary text-sm font-bold">%</Text>
                                </View>
                                <View className="w-full h-1.5 bg-white/10 rounded-full mt-2 overflow-hidden">
                                    <View className="h-full bg-primary rounded-full shadow-[0_0_10px_#0d7ff2]" style={{ width: `${confidencePercent}%` }} />
                                </View>
                            </View>
                        </View>

                        <View className="flex-1 bg-surface-card border border-white/10 rounded-2xl p-4 justify-between relative overflow-hidden">
                            <Text className="text-text-dim text-xs font-medium">진단 유형</Text>
                            <View className="flex-row items-center justify-between">
                                <Text className="text-white text-xl font-bold">{triggerType}</Text>
                                <View className="w-10 h-10 rounded-full bg-white/5 items-center justify-center">
                                    <MaterialIcons name="analytics" size={20} color="#94a3b8" />
                                </View>
                            </View>
                        </View>
                    </View>

                    {/* 4. Action Guide (Prominent) */}
                    <View className="mb-6 flex-1">
                        <View className="flex-row items-center justify-between mb-3 px-1">
                            <Text className="text-white text-lg font-bold">AI 조치 가이드</Text>
                            <View className="flex-row items-center gap-1">
                                <MaterialIcons name="tips-and-updates" size={16} color="#3b82f6" />
                                <Text className="text-blue-400 text-xs font-bold">권장 사항</Text>
                            </View>
                        </View>
                        <View className="bg-gradient-to-br from-[#1e2936] to-[#151f2b] p-6 rounded-3xl border border-blue-500/20 shadow-lg min-h-[160px]">
                            <Text className="text-white/90 text-[16px] leading-[26px] font-medium tracking-wide">
                                {finalGuide}
                            </Text>
                        </View>
                    </View>

                    {/* 5. Suspected Causes (Collapsible/Detailed) - Optional if guide covers it, but keeping it for detail */}
                    {suspectedCauses.length > 0 && (
                        <View className="mb-6">
                            <Text className="text-white text-lg font-bold mb-3 px-1">상세 원인 분석</Text>
                            {suspectedCauses.map((item: any, index: number) => (
                                <View key={index} className="bg-surface-card border border-white/5 rounded-2xl p-4 mb-3">
                                    <View className="flex-row items-start justify-between mb-2">
                                        <View className="flex-row items-center gap-3 flex-1">
                                            <View className="w-6 h-6 rounded-full bg-white/10 items-center justify-center border border-white/10">
                                                <Text className="text-white text-xs font-bold">{index + 1}</Text>
                                            </View>
                                            <Text className="text-white font-bold text-base flex-1">{item.cause}</Text>
                                        </View>
                                        {item.reliability && (
                                            <View className={`px-2 py-0.5 rounded border ${item.reliability === 'HIGH' ? 'bg-success/10 border-success/30' :
                                                'bg-warning/10 border-warning/30'
                                                }`}>
                                                <Text className={`text-[10px] font-bold ${item.reliability === 'HIGH' ? 'text-success' : 'text-warning'
                                                    }`}>
                                                    {item.reliability}
                                                </Text>
                                            </View>
                                        )}
                                    </View>
                                    <Text className="text-text-muted text-sm pl-9 leading-5">{item.basis}</Text>
                                </View>
                            ))}
                        </View>
                    )}
                </View>
            </ScrollView>

            {/* Top Navigation - Moved outside ScrollView and Image container */}
            <View className="absolute top-0 inset-x-0 z-50 px-4 flex-row items-center justify-between" style={{ paddingTop: insets.top + 10 }}>
                <TouchableOpacity onPress={handleBack} className="w-10 h-10 items-center justify-center bg-black/40 rounded-full border border-white/10 backdrop-blur-md">
                    <MaterialIcons name="arrow-back" size={24} color="white" />
                </TouchableOpacity>
                <View className="px-3 py-1 bg-black/40 rounded-full border border-white/10 backdrop-blur-md">
                    <Text className="text-white/90 text-xs font-bold tracking-widest uppercase">AI Diagnosis Report</Text>
                </View>
                <View className="w-10" />
            </View>

            {/* Bottom Action Button (Fixed) */}
            <View className="absolute bottom-0 inset-x-0 z-50 p-5 bg-background-dark/80 backdrop-blur-xl border-t border-white/5" style={{ paddingBottom: insets.bottom + 20 }}>
                <TouchableOpacity
                    onPress={handleFinish}
                    activeOpacity={0.9}
                    className="h-14 rounded-2xl overflow-hidden shadow-2xl shadow-primary/20"
                >
                    <LinearGradient
                        colors={['#0d7ff2', '#2563eb']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        className="w-full h-full flex-row items-center justify-center gap-2"
                    >
                        <Text className="text-white text-lg font-bold">
                            {route.params?.fromHistory ? '확인' : '진단 결과 확인 완료'}
                        </Text>
                        <MaterialIcons name={route.params?.fromHistory ? 'check' : 'arrow-forward'} size={22} color="white" />
                    </LinearGradient>
                </TouchableOpacity>
            </View>
            {insets.bottom > 0 && (
                <View
                    style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: insets.bottom,
                        backgroundColor: '#101922',
                    }}
                />
            )}
        </View>
    );
}
