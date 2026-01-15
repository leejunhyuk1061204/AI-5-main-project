import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, TextInput, StyleSheet, Platform, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { CommonActions } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function ActiveSuccess({ navigation }: any) {
    const [vehicleNumber, setVehicleNumber] = useState('');
    const insets = useSafeAreaInsets();

    const handleGoHome = () => {
        navigation.dispatch(
            CommonActions.reset({
                index: 0,
                routes: [{ name: 'MainPage' }],
            })
        );
    };

    return (
        <View style={[styles.container, { paddingTop: insets.top }]}>
            <StatusBar style="light" />

            <View style={styles.header}>
                <Text style={styles.headerTitle}>차량 등록 결과</Text>
                <View style={{ width: 40 }} />
            </View>

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
            >
                <View style={styles.successIconContainer}>
                    <MaterialIcons name="check-circle" size={80} color="#0d7ff2" style={styles.shadowIcon} />
                </View>

                <Text style={styles.title}>차량 등록이{'\n'}완료되었습니다!</Text>
                <Text style={styles.subtitle}>제네시스 GV80 차량 정보가 등록되었습니다.</Text>

                <View style={styles.card}>
                    <View style={styles.cardRow}>
                        <View style={[styles.cardItem, styles.borderRight]}>
                            <Text style={styles.cardLabel}>모델명</Text>
                            <Text style={styles.cardValue} numberOfLines={1}>Genesis GV80</Text>
                        </View>
                        <View style={styles.cardItem}>
                            <Text style={styles.cardLabel}>연식</Text>
                            <Text style={styles.cardValue}>2023년형</Text>
                        </View>
                    </View>
                    <View style={styles.cardRow}>
                        <View style={[styles.cardItem, styles.borderRight]}>
                            <Text style={styles.cardLabel}>배기량</Text>
                            <Text style={styles.cardValue}>2,497cc</Text>
                        </View>
                        <View style={styles.cardItem}>
                            <Text style={styles.cardLabel}>연료 타입</Text>
                            <Text style={styles.cardValue}>가솔린</Text>
                        </View>
                    </View>
                </View>

                {/* Input Section */}
                <View style={styles.inputContainer}>
                    <Text style={styles.label}>차량 번호 입력</Text>
                    <TextInput
                        value={vehicleNumber}
                        onChangeText={setVehicleNumber}
                        placeholder="예: 12가 3456"
                        placeholderTextColor="#94a3b8"
                        style={styles.input}
                    />
                    <Text style={styles.helperText}>
                        차량 번호를 입력해야 홈으로 이동할 수 있습니다.
                    </Text>
                </View>

                {/* Checklist */}
                <View style={styles.checklistContainer}>
                    <View style={styles.checklistItem}>
                        <View style={[styles.iconCircle, { backgroundColor: 'rgba(16, 185, 129, 0.1)' }]}>
                            <MaterialIcons name="fact-check" size={24} color="#10b981" />
                        </View>
                        <Text style={styles.checklistText}>차대번호(VIN) 조회 및 매칭 성공</Text>
                        <MaterialIcons name="check" size={20} color="#64748b" />
                    </View>
                    <View style={styles.checklistItem}>
                        <View style={[styles.iconCircle, { backgroundColor: 'rgba(13, 127, 242, 0.1)' }]}>
                            <MaterialIcons name="settings-backup-restore" size={24} color="#0d7ff2" />
                        </View>
                        <Text style={styles.checklistText}>제조사 권장 소모품 주기 적용</Text>
                        <MaterialIcons name="check" size={20} color="#64748b" />
                    </View>
                </View>

                <TouchableOpacity
                    style={[styles.buttonWrapper, !vehicleNumber && { opacity: 0.5 }]}
                    onPress={handleGoHome}
                    disabled={!vehicleNumber}
                    activeOpacity={0.9}
                >
                    <LinearGradient
                        colors={!vehicleNumber ? ['#64748b', '#475569'] : ['#0d7ff2', '#06b6d4']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        style={styles.gradientButton}
                    >
                        <Text style={styles.buttonText}>홈으로 이동</Text>
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
