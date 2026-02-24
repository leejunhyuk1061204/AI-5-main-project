import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    TouchableOpacity,
    ScrollView,
    Modal,
    TextInput,
    Pressable,
    FlatList,
    KeyboardAvoidingView,
    Platform,
    ActivityIndicator,
    StyleSheet
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { format } from 'date-fns';
import { useRegistrationStore } from '../../store/useRegistrationStore';
import { useConsumableStore } from '../../store/useConsumableStore';
import { useAlertStore } from '../../store/useAlertStore';
import { useDatePickerStore } from '../../store/useDatePickerStore';
import { isPositionTypeCode, getPositionOptions } from '../../maintenance/consumableItems';

const BOTTOM_BAR_HEIGHT = 156;

export default function MaintenanceReg() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const store = useRegistrationStore();
    const datePickerStore = useDatePickerStore();
    const consumablePickerList = useConsumableStore((s) => s.consumablePickerList);
    const getConsumableMasterItem = useConsumableStore((s) => s.getConsumableMasterItem);

    // UI State
    const [modalVisible, setModalVisible] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [positionModalVisible, setPositionModalVisible] = useState(false);
    const [positionTypeCode, setPositionTypeCode] = useState<'TIRE_POSITION' | 'BRAKE_POSITION' | null>(null);
    const [selectedPositionCodes, setSelectedPositionCodes] = useState<string[]>([]);

    useEffect(() => {
        const init = async () => {
            await store.loadConsumableMaster();
            store.addDefaultConsumables();
        };
        init();
    }, []);

    // Helper: Handle Registration
    const handleComplete = async (isSkip: boolean = false) => {
        if (!isSkip) {
            // Check if at least one record exists that user interacted with
            const hasValidRecord = store.maintenanceRecords.some(r => r.lastReplacementDate || r.lastReplacementMileage);
            if (!hasValidRecord && store.maintenanceRecords.length > 0) {
                useAlertStore.getState().showAlert('알림', '최소 하나의 소모품 정보를 입력해주세요.', 'ERROR');
                return;
            }

            // 모든 추가된 레코드에 대해 "km(주행거리)"가 누락된 항목이 있는지 검사
            const missingMileageRecords = store.maintenanceRecords.filter(
                (r) => (r.lastReplacementDate || r.lastReplacementMileage) && !r.lastReplacementMileage
            );

            if (missingMileageRecords.length > 0) {
                const names = missingMileageRecords.map((r) => r.itemName).join(', ');
                useAlertStore.getState().showAlert(
                    '입력 누락',
                    `${names} 항목의 교체 시점 주행거리(km)를 반드시 입력해주세요.`,
                    'WARNING'
                );
                return;
            }
        }

        const result = await store.registerAll();
        if (result.success) {
            useAlertStore.getState().showAlert('등록 완료', '차량과 정비 이력이 성공적으로 등록되었습니다.', 'SUCCESS', () => {
                navigation.navigate('MainPage');
            });
        } else {
            useAlertStore.getState().showAlert('오류', result.message || '등록 중 문제가 발생했습니다.', 'ERROR');
        }
    };

    const filteredMasterList = consumablePickerList.filter(item => {
        const query = searchQuery.toLowerCase();
        return item.name.toLowerCase().includes(query);
    });

    const togglePosition = (code: string) => {
        setSelectedPositionCodes(prev =>
            prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
        );
    };

    const openPositionModal = (code: 'TIRE_POSITION' | 'BRAKE_POSITION') => {
        setPositionTypeCode(code);
        setSelectedPositionCodes([]);
        setPositionModalVisible(true);
    };

    const confirmPositionSelection = () => {
        if (!positionTypeCode || selectedPositionCodes.length === 0) {
            useAlertStore.getState().showAlert('알림', '최소 1개 위치를 선택해주세요.', 'INFO');
            return;
        }
        selectedPositionCodes.forEach(code => {
            const item = getConsumableMasterItem(code);
            if (item) store.addMaintenanceRecord(item);
        });
        setPositionModalVisible(false);
        setModalVisible(false);
        setPositionTypeCode(null);
        setSelectedPositionCodes([]);
    };

    // Helper: Date Picker
    const showDatePicker = (itemCode: string) => {
        datePickerStore.openDatePicker({
            mode: 'date',
            initialDate: new Date(),
            onConfirm: (date) => {
                store.updateMaintenanceRecord(itemCode, 'date', format(date, 'yyyy-MM-dd'));
            }
        });
    };

    // Render Consumable Item Card (Input Form)
    const renderRecordCard = (item: typeof store.maintenanceRecords[0]) => {
        return (
            <View key={item.itemCode} style={styles.card}>
                <View style={styles.cardHeader}>
                    <Text style={styles.cardTitle}>{item.itemName}</Text>
                    <TouchableOpacity onPress={() => store.removeMaintenanceRecord(item.itemCode)} style={styles.removeButton}>
                        <MaterialIcons name="close" size={20} color="#94a3b8" />
                    </TouchableOpacity>
                </View>

                <View style={styles.cardInputs}>
                    {/* Date Input */}
                    <TouchableOpacity
                        style={styles.inputFlex}
                        onPress={() => showDatePicker(item.itemCode)}
                    >
                        <Text style={styles.inputLabel}>마지막 교체일</Text>
                        <View style={styles.inputBox}>
                            <MaterialIcons name="event" size={18} color="#94a3b8" />
                            <Text style={[styles.inputText, !item.lastReplacementDate && styles.placeholderText]}>
                                {item.lastReplacementDate || '날짜 선택'}
                            </Text>
                        </View>
                    </TouchableOpacity>

                    {/* Mileage Input */}
                    <View style={styles.inputFlex}>
                        <Text style={styles.inputLabel}>교체 시점 주행거리</Text>
                        <View style={styles.inputBox}>
                            <MaterialIcons name="speed" size={18} color="#94a3b8" />
                            <TextInput
                                value={item.lastReplacementMileage}
                                onChangeText={(t) => store.updateMaintenanceRecord(item.itemCode, 'mileage', t.replace(/[^0-9]/g, ''))}
                                placeholder="0"
                                placeholderTextColor="#64748b"
                                keyboardType="number-pad"
                                style={styles.textInputField}
                            />
                            <Text style={styles.unitText}>km</Text>
                        </View>
                    </View>
                </View>
            </View>
        );
    };

    return (
        <View style={[styles.container, { flex: 1 }]}>
            <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right', 'bottom']}>
            <StatusBar style="light" />

            {/* Header */}
            <View style={styles.header}>
                <View style={styles.headerContent}>
                    <TouchableOpacity
                        style={styles.backButton}
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="white" />
                    </TouchableOpacity>
                    <Text style={styles.headerTitle}>소모품 교체 이력</Text>
                    <View style={{ width: 40 }} />
                </View>
            </View>

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={[styles.scrollContent, { paddingBottom: BOTTOM_BAR_HEIGHT }]}
            >
                <View style={styles.titleSection}>
                    <Text style={styles.mainTitle}>최근 정비한 내역이 있나요?</Text>
                    <Text style={styles.subTitle}>AI가 다음 교체 시기를 예측해드립니다.</Text>
                    <Text style={styles.tipText}>* 교체 시점의 주행거리(km)는 필수 입력 사항입니다.</Text>
                </View>

                {/* List of Added Records */}
                {store.maintenanceRecords.map(item => renderRecordCard(item))}

                {/* Add Button */}
                <TouchableOpacity
                    onPress={() => setModalVisible(true)}
                    style={styles.addButton}
                >
                    <MaterialIcons name="add-circle-outline" size={24} color="#3b82f6" />
                    <Text style={styles.addButtonText}>소모품 추가하기</Text>
                </TouchableOpacity>
            </ScrollView>

            {/* 하단 고정: 등록 / 건너뛰기 (스크롤 시 리스트가 버튼 아래로 비치지 않도록 scrollContent paddingBottom으로 여백 확보) */}
            <View style={[styles.bottomActions, { paddingBottom: Math.max(insets.bottom, 16) }]}>
                <TouchableOpacity
                    onPress={() => handleComplete(false)}
                    style={styles.registerButton}
                >
                    <Text style={styles.registerButtonText}>등록</Text>
                    <MaterialIcons name="check" size={20} color="white" />
                </TouchableOpacity>
                <TouchableOpacity
                    onPress={() => {
                        store.clearMaintenanceRecords();
                        handleComplete(true);
                    }}
                    style={styles.skipButton}
                >
                    <Text style={styles.skipButtonText}>다음에 입력하기 (건너뛰기)</Text>
                </TouchableOpacity>
            </View>

            {/* Selection Modal */}
            <Modal
                visible={modalVisible}
                transparent={true}
                animationType="slide"
                onRequestClose={() => setModalVisible(false)}
            >
                <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
                    <Pressable style={styles.modalOverlay} onPress={() => setModalVisible(false)}>
                        <Pressable style={styles.modalContent} onPress={(e) => e.stopPropagation()}>
                            <View style={styles.modalHeader}>
                                <Text style={styles.modalTitle}>소모품 선택</Text>
                                <TouchableOpacity onPress={() => setModalVisible(false)}>
                                    <MaterialIcons name="close" size={24} color="#94a3b8" />
                                </TouchableOpacity>
                            </View>

                            <View style={styles.searchBarContainer}>
                                <View style={styles.searchBar}>
                                    <MaterialIcons name="search" size={20} color="#94a3b8" />
                                    <TextInput
                                        value={searchQuery}
                                        onChangeText={setSearchQuery}
                                        placeholder="소모품 이름 검색"
                                        placeholderTextColor="#64748b"
                                        style={styles.searchInput}
                                    />
                                </View>
                            </View>

                            <FlatList
                                data={filteredMasterList}
                                keyExtractor={(item) => item.code}
                                contentContainerStyle={{ paddingBottom: 80 }}
                                renderItem={({ item }) => {
                                    const masterItem = getConsumableMasterItem(item.code);
                                    const isPosition = isPositionTypeCode(item.code);
                                    return (
                                        <TouchableOpacity
                                            style={styles.listItem}
                                            onPress={() => {
                                                if (isPosition) {
                                                    openPositionModal(item.code as 'TIRE_POSITION' | 'BRAKE_POSITION');
                                                } else if (masterItem) {
                                                    store.addMaintenanceRecord(masterItem);
                                                    setModalVisible(false);
                                                }
                                            }}
                                        >
                                            <View>
                                                <Text style={styles.listItemName}>{item.name}</Text>
                                                <Text style={styles.listItemSub}>
                                                    {masterItem?.replacementCycleKm != null
                                                        ? `교체 주기: ${masterItem.replacementCycleKm.toLocaleString()}km`
                                                        : isPosition ? '위치 선택 시 개별 등록' : ''}
                                                </Text>
                                            </View>
                                        </TouchableOpacity>
                                    );
                                }}
                            />
                        </Pressable>
                    </Pressable>
                </KeyboardAvoidingView>
            </Modal>

            {/* 타이어/브레이크 위치 선택 모달 */}
            <Modal
                visible={positionModalVisible}
                transparent
                animationType="fade"
                onRequestClose={() => setPositionModalVisible(false)}
            >
                <Pressable style={styles.modalOverlay} onPress={() => setPositionModalVisible(false)}>
                    <Pressable style={styles.modalContent} onPress={(e) => e.stopPropagation()}>
                        <View style={styles.modalHeader}>
                            <Text style={styles.modalTitle}>
                                {positionTypeCode === 'TIRE_POSITION' ? '어느 타이어를 등록할까요?' : '어느 브레이크 패드를 등록할까요?'}
                            </Text>
                            <TouchableOpacity onPress={() => setPositionModalVisible(false)}>
                                <MaterialIcons name="close" size={24} color="#94a3b8" />
                            </TouchableOpacity>
                        </View>
                        <View style={styles.positionModalBody}>
                            <Text style={[styles.subTitle, styles.positionModalSubtitle]}>복수 선택 가능</Text>
                            <View style={styles.positionOptionsGrid}>
                                {positionTypeCode && getPositionOptions(positionTypeCode).map((opt) => (
                                    <TouchableOpacity
                                        key={opt.code}
                                        style={[
                                            styles.positionOptionChip,
                                            selectedPositionCodes.includes(opt.code) && styles.positionOptionChipSelected
                                        ]}
                                        onPress={() => togglePosition(opt.code)}
                                    >
                                        <MaterialIcons
                                            name={selectedPositionCodes.includes(opt.code) ? 'check-box' : 'check-box-outline-blank'}
                                            size={22}
                                            color={selectedPositionCodes.includes(opt.code) ? '#3b82f6' : '#64748b'}
                                        />
                                        <Text style={styles.positionOptionLabel}>{opt.name}</Text>
                                    </TouchableOpacity>
                                ))}
                            </View>
                            <View style={styles.positionModalActions}>
                                <TouchableOpacity
                                    style={[styles.positionModalButton, styles.positionModalButtonCancel]}
                                    onPress={() => setPositionModalVisible(false)}
                                >
                                    <Text style={styles.listItemName}>취소</Text>
                                </TouchableOpacity>
                                <TouchableOpacity
                                    style={[
                                        styles.positionModalButton,
                                        styles.positionModalButtonConfirm,
                                        selectedPositionCodes.length === 0 && styles.positionModalButtonDisabled
                                    ]}
                                    onPress={confirmPositionSelection}
                                    disabled={selectedPositionCodes.length === 0}
                                >
                                    <Text style={[styles.listItemName, selectedPositionCodes.length === 0 && { color: '#64748b' }]}>선택 완료</Text>
                                </TouchableOpacity>
                            </View>
                        </View>
                    </Pressable>
                </Pressable>
            </Modal>

            {/* Loading Overlay */}
            {store.isLoading && (
                <View style={styles.loadingOverlay}>
                    <View style={styles.loadingBox}>
                        <ActivityIndicator size="large" color="#3b82f6" />
                        <Text style={styles.loadingText}>등록 중입니다...</Text>
                    </View>
                </View>
            )}
            </SafeAreaView>
            {insets.bottom > 0 && (
                <View
                    style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: insets.bottom,
                        backgroundColor: '#111827',
                    }}
                />
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#111827', // bg-background-dark
    },
    header: {
        backgroundColor: 'rgba(17, 24, 39, 0.8)',
    },
    headerContent: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 16,
        paddingVertical: 12,
        paddingBottom: 16,
    },
    backButton: {
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 20,
    },
    headerTitle: {
        color: 'white',
        fontSize: 18,
        fontWeight: 'bold',
        textAlign: 'center',
        flex: 1,
    },
    scrollView: {
        flex: 1,
        paddingHorizontal: 20,
    },
    scrollContent: {
        paddingBottom: 24,
    },
    bottomActions: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        paddingHorizontal: 20,
        paddingTop: 20,
        backgroundColor: '#111827',
    },
    titleSection: {
        marginTop: 8,
        marginBottom: 24,
    },
    mainTitle: {
        color: 'white',
        fontSize: 20,
        fontWeight: 'bold',
        marginBottom: 8,
    },
    subTitle: {
        color: '#94a3b8',
        fontSize: 14,
        lineHeight: 20,
    },
    tipText: {
        color: 'rgba(57, 131, 246, 0.8)',
        fontSize: 12,
        marginTop: 12,
        fontWeight: '500',
    },
    card: {
        backgroundColor: '#1e293b', // surface-card
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 16,
        padding: 16,
        marginBottom: 16,
    },
    cardHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
    },
    cardTitle: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 16,
    },
    removeButton: {
        padding: 4,
    },
    cardInputs: {
        flexDirection: 'row',
        gap: 12,
    },
    inputFlex: {
        flex: 1,
    },
    inputLabel: {
        fontSize: 12,
        color: '#94a3b8',
        marginBottom: 4,
        marginLeft: 4,
    },
    inputBox: {
        height: 48,
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 8,
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 12,
    },
    inputText: {
        marginLeft: 8,
        fontSize: 14,
        color: 'white',
    },
    placeholderText: {
        color: '#64748b',
    },
    textInputField: {
        flex: 1,
        marginLeft: 8,
        color: 'white',
        fontSize: 14,
        height: '100%',
    },
    unitText: {
        fontSize: 12,
        color: '#64748b',
    },
    addButton: {
        width: '100%',
        paddingVertical: 16,
        borderWidth: 1,
        borderStyle: 'dashed',
        borderColor: 'rgba(255, 255, 255, 0.2)',
        borderRadius: 16,
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'row',
        gap: 8,
        marginBottom: 32,
    },
    addButtonText: {
        color: '#3b82f6',
        fontWeight: 'bold',
    },
    registerButton: {
        width: '100%',
        height: 56,
        backgroundColor: '#3b82f6',
        borderRadius: 16,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        marginBottom: 12,
        elevation: 4,
        shadowColor: 'rgba(59, 130, 246, 0.3)',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 1,
        shadowRadius: 10,
    },
    registerButtonText: {
        color: 'white',
        fontWeight: 'bold',
        fontSize: 18,
    },
    skipButton: {
        width: '100%',
        height: 48,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
    },
    skipButtonText: {
        color: '#94a3b8',
        fontWeight: '500',
        fontSize: 16,
        textDecorationLine: 'underline',
    },
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        backgroundColor: '#111827',
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        height: '70%',
    },
    modalHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: 16,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(255, 255, 255, 0.1)',
    },
    modalTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: 'white',
    },
    searchBarContainer: {
        paddingHorizontal: 16,
        paddingVertical: 12,
    },
    searchBar: {
        backgroundColor: '#1e293b',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 12,
        height: 48,
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 12,
    },
    searchInput: {
        flex: 1,
        marginLeft: 8,
        color: 'white',
        fontSize: 16,
    },
    listItem: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 16,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(255, 255, 255, 0.05)',
    },
    listItemName: {
        color: 'white',
        fontWeight: '500',
        fontSize: 16,
    },
    listItemSub: {
        color: '#94a3b8',
        fontSize: 12,
        marginTop: 2,
    },
    positionModalBody: {
        paddingHorizontal: 20,
        paddingTop: 8,
        paddingBottom: 24,
    },
    positionModalSubtitle: {
        marginBottom: 16,
    },
    positionOptionsGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 12,
    },
    positionOptionChip: {
        flexDirection: 'row',
        alignItems: 'center',
        width: '48%',
        paddingVertical: 14,
        paddingHorizontal: 16,
        backgroundColor: '#1e293b',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 12,
        gap: 10,
    },
    positionOptionChipSelected: {
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgba(59, 130, 246, 0.5)',
    },
    positionOptionLabel: {
        color: 'white',
        fontWeight: '500',
        fontSize: 15,
    },
    positionModalActions: {
        flexDirection: 'row',
        gap: 12,
        marginTop: 24,
    },
    positionModalButton: {
        flex: 1,
        paddingVertical: 16,
        borderRadius: 12,
        alignItems: 'center',
        justifyContent: 'center',
    },
    positionModalButtonCancel: {
        backgroundColor: '#1e293b',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.1)',
    },
    positionModalButtonConfirm: {
        backgroundColor: 'rgba(59, 130, 246, 0.3)',
    },
    positionModalButtonDisabled: {
        opacity: 0.7,
    },
    loadingOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
    },
    loadingBox: {
        backgroundColor: '#1e293b',
        padding: 24,
        borderRadius: 16,
        alignItems: 'center',
    },
    loadingText: {
        color: 'white',
        marginTop: 16,
        fontWeight: 'bold',
    },
});
