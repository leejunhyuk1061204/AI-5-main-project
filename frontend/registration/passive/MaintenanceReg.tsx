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
import { useAlertStore } from '../../store/useAlertStore';
import { useDatePickerStore } from '../../store/useDatePickerStore';

export default function MaintenanceReg() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const store = useRegistrationStore();
    const datePickerStore = useDatePickerStore();

    // UI State
    const [modalVisible, setModalVisible] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        const init = async () => {
            await store.loadConsumableMaster();
            store.addDefaultConsumables();
        };
        init();
    }, []);

    // Helper: Handle Registration
    const handleComplete = async () => {
        const result = await store.registerAll();
        if (result.success) {
            useAlertStore.getState().showAlert('등록 완료', '차량과 정비 이력이 성공적으로 등록되었습니다.', 'SUCCESS', () => {
                navigation.navigate('MainPage');
            });
        } else {
            useAlertStore.getState().showAlert('오류', result.message || '등록 중 문제가 발생했습니다.', 'ERROR');
        }
    };

    // Helper: Filter Master List
    const filteredMasterList = store.consumableMasterList.filter(item => {
        const query = searchQuery.toLowerCase();
        return item.name.toLowerCase().includes(query) || (item.category && item.category.toLowerCase().includes(query));
    });

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
        <View style={styles.container}>
            <StatusBar style="light" />

            {/* Header */}
            <View style={[styles.header, { paddingTop: insets.top }]}>
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

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
                <View style={styles.titleSection}>
                    <Text style={styles.mainTitle}>최근 정비한 내역이 있나요?</Text>
                    <Text style={styles.subTitle}>AI가 다음 교체 시기를 예측해드립니다.</Text>
                    <Text style={styles.tipText}>* 날짜 또는 주행거리 중 하나만 입력해도 됩니다.</Text>
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

            {/* Bottom Actions */}
            <View style={[styles.bottomActions, { paddingBottom: insets.bottom + 16 }]}>
                <TouchableOpacity
                    onPress={handleComplete}
                    style={styles.registerButton}
                >
                    <Text style={styles.registerButtonText}>등록</Text>
                    <MaterialIcons name="check" size={20} color="white" />
                </TouchableOpacity>

                <TouchableOpacity
                    onPress={() => {
                        store.clearMaintenanceRecords();
                        handleComplete();
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
                                renderItem={({ item }) => (
                                    <TouchableOpacity
                                        style={styles.listItem}
                                        onPress={() => {
                                            store.addMaintenanceRecord(item);
                                            setModalVisible(false);
                                        }}
                                    >
                                        <View>
                                            <Text style={styles.listItemName}>{item.name}</Text>
                                            <Text style={styles.listItemSub}>
                                                교체 주기: {item.replacementCycleKm?.toLocaleString()}km
                                            </Text>
                                        </View>
                                    </TouchableOpacity>
                                )}
                            />
                        </Pressable>
                    </Pressable>
                </KeyboardAvoidingView>
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
        paddingBottom: 120,
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
    bottomActions: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: 20,
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
