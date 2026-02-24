import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, TextInput, StyleSheet, Platform, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { CommonActions } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

export default function ObdDiagResult({ navigation, route }: any) {
    const params = route.params || {};
    const insets = useSafeAreaInsets();

    const handleGoHome = () => {
        navigation.navigate('MainPage');
    };

    return (
        <View style={[styles.container, { flex: 1 }]}>
            <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right', 'bottom']}>
            <StatusBar style="light" />

            <View style={styles.header}>
                <Text style={styles.headerTitle}>진단 결과</Text>
                <View style={{ width: 40 }} />
            </View>

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
            >
                <View style={styles.successIconContainer}>
                    <MaterialIcons name="check-circle" size={80} color="#0d7ff2" style={styles.shadowIcon} />
                </View>

                <Text style={styles.title}>차량 진단이{'\n'}완료되었습니다</Text>
                <Text style={styles.subtitle}>모든 주요 시스템이 정상 작동 중입니다.</Text>

                <View style={styles.card}>
                    <View style={styles.cardRow}>
                        <View style={[styles.cardItem, styles.borderRight]}>
                            <Text style={styles.cardLabel}>엔진 상태</Text>
                            <Text style={styles.cardValue} numberOfLines={1}>정상</Text>
                        </View>
                        <View style={styles.cardItem}>
                            <Text style={styles.cardLabel}>DTC 코드</Text>
                            <Text style={styles.cardValue}>없음</Text>
                        </View>
                    </View>
                    <View style={styles.cardRow}>
                        <View style={[styles.cardItem, styles.borderRight]}>
                            <Text style={styles.cardLabel}>배터리 전압</Text>
                            <Text style={styles.cardValue}>12.4V</Text>
                        </View>
                        <View style={styles.cardItem}>
                            <Text style={styles.cardLabel}>냉각수 온도</Text>
                            <Text style={styles.cardValue}>90°C</Text>
                        </View>
                    </View>
                </View>

                {/* Checklist */}
                <View style={styles.checklistContainer}>
                    <View style={styles.checklistItem}>
                        <View style={[styles.iconCircle, { backgroundColor: 'rgba(16, 185, 129, 0.1)' }]}>
                            <MaterialIcons name="security" size={24} color="#10b981" />
                        </View>
                        <Text style={styles.checklistText}>주행 안전성 : 우수 (98점)</Text>
                        <MaterialIcons name="check" size={20} color="#64748b" />
                    </View>
                    <View style={styles.checklistItem}>
                        <View style={[styles.iconCircle, { backgroundColor: 'rgba(13, 127, 242, 0.1)' }]}>
                            <MaterialIcons name="build" size={24} color="#0d7ff2" />
                        </View>
                        <Text style={styles.checklistText}>소모품 상태 : 양호</Text>
                        <MaterialIcons name="check" size={20} color="#64748b" />
                    </View>
                </View>

                <TouchableOpacity
                    style={[styles.buttonWrapper]}
                    onPress={handleGoHome}
                    activeOpacity={0.9}
                >
                    <LinearGradient
                        colors={['#0d7ff2', '#06b6d4']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        style={styles.gradientButton}
                    >
                        <Text style={styles.buttonText}>홈으로</Text>
                        <MaterialIcons name="home" size={24} color="white" />
                    </LinearGradient>
                </TouchableOpacity>

            </ScrollView>
            </SafeAreaView>
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
    closeButton: {
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 20,
        backgroundColor: '#1e2936',
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
        fontSize: 14,
        textTransform: 'uppercase',
        letterSpacing: 1,
        marginBottom: 4,
    },
    cardValue: {
        color: 'white',
        fontSize: 16,
        fontWeight: '700',
    },
    inputContainer: {
        marginBottom: 32,
    },
    label: {
        color: '#94a3b8',
        fontSize: 14,
        fontWeight: '500',
        marginBottom: 8,
        marginLeft: 4,
    },
    input: {
        height: 56,
        backgroundColor: '#1e2936',
        borderWidth: 1,
        borderColor: '#2d3b4e',
        borderRadius: 12,
        paddingHorizontal: 16,
        color: 'white',
        fontSize: 16,
    },
    helperText: {
        color: '#64748b',
        fontSize: 12,
        marginTop: 8,
        marginLeft: 4,
    },
    checklistContainer: {
        gap: 16,
        marginBottom: 40,
    },
    checklistItem: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#1e2936',
        padding: 16,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: '#2d3b4e',
    },
    iconCircle: {
        width: 48,
        height: 48,
        borderRadius: 24,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 16,
    },
    checklistText: {
        flex: 1,
        color: 'white',
        fontSize: 16,
        fontWeight: '600',
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
