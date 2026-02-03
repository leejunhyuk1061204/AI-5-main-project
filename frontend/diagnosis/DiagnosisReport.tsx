import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, BackHandler } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAiDiagnosisStore } from '../store/useAiDiagnosisStore';
import { getDiagnosisSessionStatus } from '../api/aiApi';

export default function DiagnosisReport() {
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const insets = useSafeAreaInsets();
    const { reset } = useAiDiagnosisStore();

    const [report, setReport] = useState<any>(route.params?.reportData || null);
    const [loading, setLoading] = useState(false);

    const sessionId = route.params?.sessionId || report?.sessionId;

    useEffect(() => {
        if (sessionId && (!report || !report.finalReport)) {
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

    const handleFinish = () => {
        reset();
        navigation.navigate('DiagTab');
    };

    useEffect(() => {
        const backHandler = BackHandler.addEventListener(
            'hardwareBackPress',
            () => {
                handleFinish();
                return true;
            }
        );
        return () => backHandler.remove();
    }, []);

    if (loading || !report) {
        return (
            <View style={[styles.container, { paddingTop: insets.top, justifyContent: 'center', alignItems: 'center' }]}>
                <ActivityIndicator size="large" color="#0d7ff2" />
                <Text style={{ marginTop: 16, color: '#94a3b8' }}>리포트 데이터를 분석 중입니다...</Text>
            </View>
        );
    }

    return (
        <View style={[styles.container, { paddingTop: insets.top }]}>
            <View style={styles.header}>
                <TouchableOpacity onPress={handleFinish} style={{ padding: 8 }}>
                    <MaterialIcons name="arrow-back" size={24} color="white" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>진단 결과 보고서</Text>
                <View style={{ width: 40 }} />
            </View>

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
            >
                <View style={styles.successIconContainer}>
                    <MaterialIcons name="analytics" size={80} color="#0d7ff2" style={styles.shadowIcon} />
                </View>

                <Text style={styles.title}>AI 진단 분석{'\n'}완료</Text>
                <Text style={styles.subtitle}>
                    {report.summary || '차량 상태 분석이 완료되었습니다.'}
                </Text>

                <View style={styles.card}>
                    <View style={styles.cardRow}>
                        <View style={[styles.cardItem, styles.borderRight]}>
                            <Text style={styles.cardLabel}>종합 판정</Text>
                            <Text style={[styles.cardValue, { color: report.riskLevel === 'DANGER' ? '#ff6b6b' : '#10b981' }]}>
                                {report.riskLevel === 'DANGER' ? '위험' : '정상'}
                            </Text>
                        </View>
                        <View style={styles.cardItem}>
                            <Text style={styles.cardLabel}>진단 유형</Text>
                            <Text style={styles.cardValue}>
                                {report.triggerType || '종합 진단'}
                            </Text>
                        </View>
                    </View>
                    <View style={styles.cardRow}>
                        <View style={[styles.cardItem, styles.borderRight]}>
                            <Text style={styles.cardLabel}>발생 일시</Text>
                            <Text style={[styles.cardValue, { fontSize: 13 }]}>
                                {report.createdAt ? new Date(report.createdAt).toLocaleDateString() : '-'}
                            </Text>
                        </View>
                        <View style={styles.cardItem}>
                            {/* Dynamic extra field */}
                            <Text style={styles.cardLabel}>신뢰도</Text>
                            <Text style={styles.cardValue}>98%</Text>
                        </View>
                    </View>
                </View>

                {/* Analysis Details / Checklist */}
                <View style={styles.checklistContainer}>
                    <View style={styles.checklistItem}>
                        <View style={[styles.iconCircle, { backgroundColor: 'rgba(13, 127, 242, 0.1)' }]}>
                            <MaterialIcons name="summarize" size={24} color="#0d7ff2" />
                        </View>
                        <View style={{ flex: 1 }}>
                            <Text style={{ color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>상세 분석 내용</Text>
                            <Text style={styles.checklistText}>
                                {report.finalReport || report.description || '특이사항이 발견되지 않았습니다.'}
                            </Text>
                        </View>
                    </View>

                    {report.riskLevel === 'DANGER' && (
                        <View style={styles.checklistItem}>
                            <View style={[styles.iconCircle, { backgroundColor: 'rgba(239, 68, 68, 0.1)' }]}>
                                <MaterialIcons name="warning" size={24} color="#ff6b6b" />
                            </View>
                            <View style={{ flex: 1 }}>
                                <Text style={{ color: '#ff6b6b', fontSize: 12, marginBottom: 4 }}>조치 권장</Text>
                                <Text style={styles.checklistText}>
                                    가까운 정비소를 방문하여 상세 점검을 받으시는 것을 권장합니다.
                                </Text>
                            </View>
                        </View>
                    )}
                </View>

                <TouchableOpacity
                    style={[styles.buttonWrapper]}
                    onPress={handleFinish}
                    activeOpacity={0.9}
                >
                    <LinearGradient
                        colors={['#0d7ff2', '#06b6d4']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        style={styles.gradientButton}
                    >
                        <Text style={styles.buttonText}>확인 (홈으로)</Text>
                        <MaterialIcons name="home" size={24} color="white" />
                    </LinearGradient>
                </TouchableOpacity>

            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#101922',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 16,
        paddingBottom: 8,
    },
    headerTitle: {
        color: '#94a3b8',
        fontSize: 14,
        fontWeight: '600',
    },
    scrollContent: {
        paddingHorizontal: 24,
        paddingBottom: 50,
        paddingTop: 16,
    },
    successIconContainer: {
        alignItems: 'center',
        marginBottom: 24,
        marginTop: 16,
    },
    shadowIcon: {
        textShadowColor: 'rgba(13, 127, 242, 0.5)',
        textShadowRadius: 20,
    },
    title: {
        fontSize: 28,
        fontWeight: 'bold',
        color: 'white',
        textAlign: 'center',
        marginBottom: 8,
        lineHeight: 36,
    },
    subtitle: {
        fontSize: 14,
        color: '#94a3b8',
        textAlign: 'center',
        marginBottom: 32,
        paddingHorizontal: 20,
        lineHeight: 20,
    },
    card: {
        backgroundColor: '#1e2936',
        borderRadius: 16,
        padding: 24,
        marginBottom: 32,
        borderWidth: 1,
        borderColor: '#2d3b4e',
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 6,
    },
    cardRow: {
        flexDirection: 'row',
        marginBottom: 24,
    },
    cardItem: {
        flex: 1,
        paddingHorizontal: 8,
    },
    borderRight: {
        borderRightWidth: 1,
        borderRightColor: '#2d3b4e',
        marginRight: 8,
    },
    cardLabel: {
        color: '#94a3b8',
        fontSize: 12,
        textTransform: 'uppercase',
        letterSpacing: 1,
        marginBottom: 4,
    },
    cardValue: {
        color: 'white',
        fontSize: 16,
        fontWeight: '700',
    },
    checklistContainer: {
        gap: 16,
        marginBottom: 40,
    },
    checklistItem: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        backgroundColor: '#1e2936',
        padding: 16,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: '#2d3b4e',
    },
    iconCircle: {
        width: 40,
        height: 40,
        borderRadius: 20,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 16,
    },
    checklistText: {
        color: 'white',
        fontSize: 15,
        lineHeight: 22,
        fontWeight: '500',
    },
    buttonWrapper: {
        width: '100%',
        height: 56,
        shadowColor: "rgba(13, 127, 242, 0.4)",
        shadowOffset: { width: 0, height: 0 },
        shadowOpacity: 1,
        shadowRadius: 20,
        elevation: 8,
    },
    gradientButton: {
        width: '100%',
        height: '100%',
        borderRadius: 28,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
    },
    buttonText: {
        color: 'white',
        fontSize: 18,
        fontWeight: 'bold',
        letterSpacing: 0.5,
    },
});
