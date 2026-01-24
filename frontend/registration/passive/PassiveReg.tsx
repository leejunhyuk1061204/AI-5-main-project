import React, { useState, useEffect, useMemo } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, Modal, FlatList, Pressable, Alert, ActivityIndicator, KeyboardAvoidingView, Platform, Keyboard } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { registerVehicle } from '../../api/vehicleApi';
import { getManufacturers, getModelNames, getModelYears, getAvailableFuelTypes } from '../../api/masterApi';
import StatusModal from '../../components/StatusModal';

// Selection Type
type SelectionType = 'manufacturer' | 'model' | 'year';

// Fuel Type Labels and Icons Mapping
const FUEL_CONFIG: Record<string, { label: string, icon: keyof typeof MaterialIcons.glyphMap }> = {
    'GASOLINE': { label: '가솔린', icon: 'local-gas-station' },
    'DIESEL': { label: '디젤', icon: 'oil-barrel' },
    'EV': { label: '전기차', icon: 'electric-bolt' },
    'HEV': { label: '하이브리드', icon: 'battery-charging-full' },
    'LPG': { label: 'LPG', icon: 'gas-meter' },
    'PHEV': { label: '플러그인 하이브리드', icon: 'ev-station' },
};

export default function PassiveReg() {
    const navigation = useNavigation();
    const insets = useSafeAreaInsets();

    // Form State
    const [vehicleNumber, setVehicleNumber] = useState('');
    const [vin, setVin] = useState('');
    const [fuelType, setFuelType] = useState(''); // Default to empty

    // Master Data States
    const [manufacturer, setManufacturer] = useState('');
    const [modelName, setModelName] = useState('');
    const [modelYear, setModelYear] = useState('');

    // List Data
    const [manufacturers, setManufacturers] = useState<string[]>([]);
    const [models, setModels] = useState<string[]>([]);
    const [years, setYears] = useState<string[]>([]);
    const [availableFuels, setAvailableFuels] = useState<string[]>([]);

    // UI States
    const [loading, setLoading] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [activeType, setActiveType] = useState<SelectionType>('manufacturer');
    const [searchQuery, setSearchQuery] = useState('');

    const [registrationStatus, setRegistrationStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [resultModalVisible, setResultModalVisible] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');

    // Fetch Manufacturers on mount
    useEffect(() => {
        loadManufacturers();
    }, []);

    const loadManufacturers = async () => {
        try {
            const data = await getManufacturers();
            setManufacturers(data);
        } catch (error) {
            console.error('Failed to load manufacturers:', error);
        }
    };

    const loadModels = async (make: string) => {
        setLoading(true);
        try {
            const data = await getModelNames(make);
            setModels(data);
        } catch (error) {
            console.error('Failed to load models:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadYears = async (make: string, model: string) => {
        setLoading(true);
        try {
            const data = await getModelYears(make, model);
            setYears(data.map(y => y.toString()));
        } catch (error) {
            console.error('Failed to load years:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadAvailableFuels = async (make: string, model: string, year: string) => {
        try {
            const data = await getAvailableFuelTypes(make, model, parseInt(year));

            // Sort by priority before setting default
            const sortedData = [...data].sort((a, b) => {
                const order = ['GASOLINE', 'DIESEL', 'HEV', 'EV', 'PHEV', 'LPG'];
                const indexA = order.indexOf(a);
                const indexB = order.indexOf(b);
                return (indexA === -1 ? 99 : indexA) - (indexB === -1 ? 99 : indexB);
            });

            setAvailableFuels(data); // UI displays in original order (or sorted if preferred, but usually we want default selection to match prioritized first item)

            // Default select the top priority fuel type available
            if (sortedData.length > 0) {
                setFuelType(sortedData[0].toLowerCase());
            }
        } catch (error) {
            console.error('Failed to load fuel types:', error);
        }
    };

    // Korean Choseong (Initial Consonant) Search Logic
    const getChoseong = (str: string) => {
        const choseong = [
            'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
        ];
        let result = '';
        for (let i = 0; i < str.length; i++) {
            const code = str.charCodeAt(i) - 44032;
            if (code > -1 && code < 11172) {
                result += choseong[Math.floor(code / 588)];
            } else {
                result += str.charAt(i);
            }
        }
        return result;
    };

    // Filtered List for Search
    const filteredList = useMemo(() => {
        const currentList = activeType === 'manufacturer' ? manufacturers
            : activeType === 'model' ? models
                : years;

        if (!searchQuery) return currentList;

        const query = searchQuery.toLowerCase();
        const queryChoseong = getChoseong(query);

        return currentList.filter(item => {
            const lowerItem = item.toLowerCase();
            const itemChoseong = getChoseong(lowerItem);

            // 1. Literal search
            if (lowerItem.includes(query)) return true;

            // 2. Choseong search
            if (itemChoseong.includes(queryChoseong)) return true;

            return false;
        });
    }, [activeType, manufacturers, models, years, searchQuery]);

    // Keyboard visibility for dynamic modal height
    const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);

    useEffect(() => {
        const showSubscription = Keyboard.addListener('keyboardDidShow', () => setIsKeyboardVisible(true));
        const hideSubscription = Keyboard.addListener('keyboardDidHide', () => setIsKeyboardVisible(false));

        return () => {
            showSubscription.remove();
            hideSubscription.remove();
        };
    }, []);

    const openModal = (type: SelectionType) => {
        if (type === 'model' && !manufacturer) {
            Alert.alert('알림', '제조사를 먼저 선택해주세요.');
            return;
        }
        if (type === 'year' && !modelName) {
            Alert.alert('알림', '모델명을 먼저 선택해주세요.');
            return;
        }

        setActiveType(type);
        setSearchQuery('');
        setModalVisible(true);
    };

    const handleSelect = (item: string) => {
        if (activeType === 'manufacturer') {
            if (manufacturer !== item) {
                setManufacturer(item);
                setModelName('');
                setModelYear('');
                setAvailableFuels([]);
                setFuelType('');
                loadModels(item);
            }
        } else if (activeType === 'model') {
            if (modelName !== item) {
                setModelName(item);
                setModelYear('');
                setAvailableFuels([]);
                setFuelType('');
                loadYears(manufacturer, item);
            }
        } else if (activeType === 'year') {
            if (modelYear !== item) {
                setModelYear(item);
                loadAvailableFuels(manufacturer, modelName, item);
            }
        }
        setModalVisible(false);
    };

    const handleRegister = async () => {
        if (!vehicleNumber || !manufacturer || !modelName || !modelYear || !fuelType) {
            Alert.alert('알림', '모든 필수 필드를 입력해주세요.');
            return;
        }

        try {
            await registerVehicle({
                manufacturer,
                modelName,
                modelYear: parseInt(modelYear),
                fuelType: fuelType.toUpperCase() as any,
                carNumber: vehicleNumber,
                memo: vin ? `VIN: ${vin}` : undefined,
                nickname: `${manufacturer} ${modelName}`,
            });
            Alert.alert('성공', '차량이 성공적으로 등록되었습니다.', [
                { text: '확인', onPress: () => navigation.goBack() }
            ]);
        } catch (error) {
            console.error('Registration failed:', error);
            Alert.alert('오류', '차량 등록 중 문제가 발생했습니다. 다시 시도해주세요.');
        }
    };

    const FuelOption = ({ label, icon, value }: { label: string, icon: keyof typeof MaterialIcons.glyphMap, value: string }) => {
        const displayValue = value.toLowerCase();
        const isSelected = fuelType === displayValue;

        return (
            <Pressable
                onPress={() => setFuelType(displayValue)}
                className={`flex-row items-center justify-center h-16 rounded-xl border mb-3 px-4 transition-all duration-200 ${isSelected
                    ? 'border-primary bg-primary/10'
                    : 'border-border-dark bg-[#15181E]'
                    }`}
            >
                <MaterialIcons
                    name={icon}
                    size={22}
                    color={isSelected ? '#0d7ff2' : '#94a3b8'}
                />
                <Text className={`text-base font-medium ml-3 ${isSelected ? 'text-primary' : 'text-slate-400'}`}>
                    {label}
                </Text>
            </Pressable>
        );
    };

    return (
        <View className="flex-1 bg-[#0B0C10]">
            <StatusBar style="light" />

            {/* Header */}
            <View className="bg-[#0B0C10]/80 backdrop-blur-md z-50 sticky top-0" style={{ paddingTop: insets.top }}>
                <View className="flex-row items-center justify-between px-4 py-3 pb-4">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center rounded-full hover:bg-white/10"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="white" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold tracking-tight text-center flex-1 pr-10">
                        새 차량 등록
                    </Text>
                </View>
            </View>

            <ScrollView className="flex-1 px-5" contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
                <View className="space-y-8 mt-2">
                    {/* Vehicle Number */}
                    <View>
                        <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차량 번호</Text>
                        <TextInput
                            value={vehicleNumber}
                            onChangeText={setVehicleNumber}
                            placeholder="예: 12가 3456"
                            placeholderTextColor="#94a3b8"
                            className="w-full h-14 bg-[#15181E] border border-border-dark rounded-xl px-4 text-base text-white focus:border-primary"
                        />
                    </View>

                    {/* VIN Number */}
                    <View>
                        <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">차대번호 (VIN)</Text>
                        <View className="relative flex-row items-center">
                            <TextInput
                                value={vin}
                                onChangeText={setVin}
                                placeholder="17자리 영문+숫자"
                                placeholderTextColor="#94a3b8"
                                className="w-full h-14 bg-[#15181E] border border-border-dark rounded-xl pl-4 pr-14 text-base text-white focus:border-primary uppercase"
                            />
                            <TouchableOpacity className="absolute right-2 p-2">
                                <MaterialIcons name="center-focus-strong" size={24} color="#0d7ff2" />
                            </TouchableOpacity>
                        </View>
                    </View>

                    {/* Dropdown Fields */}
                    <View className="space-y-5">
                        {/* Manufacturer */}
                        <View>
                            <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">제조사</Text>
                            <TouchableOpacity
                                onPress={() => openModal('manufacturer')}
                                className="relative w-full h-14 bg-[#15181E] border border-border-dark rounded-xl px-4 justify-center"
                            >
                                <Text className={`text-base ${manufacturer ? 'text-white' : 'text-slate-400'}`}>
                                    {manufacturer || '제조사를 선택해주세요'}
                                </Text>
                                <View className="absolute right-4">
                                    <MaterialIcons name="expand-more" size={24} color="#94a3b8" />
                                </View>
                            </TouchableOpacity>
                        </View>

                        {/* Model Name */}
                        <View>
                            <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">모델명</Text>
                            <TouchableOpacity
                                onPress={() => openModal('model')}
                                className={`relative w-full h-14 bg-[#15181E] border border-border-dark rounded-xl px-4 justify-center ${!manufacturer && 'opacity-50'}`}
                                disabled={!manufacturer}
                            >
                                <Text className={`text-base ${modelName ? 'text-white' : 'text-slate-400'}`}>
                                    {modelName || '모델을 선택해주세요'}
                                </Text>
                                <View className="absolute right-4">
                                    <MaterialIcons name="expand-more" size={24} color="#94a3b8" />
                                </View>
                            </TouchableOpacity>
                        </View>

                        {/* Model Year */}
                        <View>
                            <Text className="text-sm font-medium text-slate-400 mb-2 pl-1">연식</Text>
                            <TouchableOpacity
                                onPress={() => openModal('year')}
                                className={`relative w-full h-14 bg-[#15181E] border border-border-dark rounded-xl px-4 justify-center ${!modelName && 'opacity-50'}`}
                                disabled={!modelName}
                            >
                                <Text className={`text-base ${modelYear ? 'text-white' : 'text-slate-400'}`}>
                                    {modelYear ? `${modelYear}년형` : '연식을 선택해주세요'}
                                </Text>
                                <View className="absolute right-4">
                                    <MaterialIcons name="expand-more" size={24} color="#94a3b8" />
                                </View>
                            </TouchableOpacity>
                        </View>
                    </View>

                    {/* Fuel Type */}
                    {availableFuels.length > 0 && (
                        <View>
                            <Text className="text-sm font-medium text-slate-400 mb-3 pl-1">연료 타입</Text>
                            <View className="flex-row flex-wrap justify-between">
                                {availableFuels
                                    .sort((a, b) => {
                                        const order = ['GASOLINE', 'DIESEL', 'HEV', 'EV', 'PHEV', 'LPG'];
                                        const indexA = order.indexOf(a);
                                        const indexB = order.indexOf(b);
                                        return (indexA === -1 ? 99 : indexA) - (indexB === -1 ? 99 : indexB);
                                    })
                                    .map((fuel) => {
                                        const config = FUEL_CONFIG[fuel] || { label: fuel, icon: 'help-outline' };
                                        return (
                                            <View
                                                key={fuel}
                                                style={{ width: availableFuels.length === 1 ? '100%' : '48.5%' }}
                                            >
                                                <FuelOption
                                                    value={fuel}
                                                    label={config.label}
                                                    icon={config.icon}
                                                />
                                            </View>
                                        );
                                    })}
                            </View>
                        </View>
                    )}
                </View>
            </ScrollView>

            <View className="absolute bottom-0 left-0 right-0 p-5 bg-gradient-to-t from-[#0B0C10] via-[#0B0C10] to-transparent" style={{ paddingBottom: insets.bottom + 10 }}>
                <TouchableOpacity
                    onPress={handleRegister}
                    className="w-full h-14 bg-primary rounded-xl shadow-lg shadow-blue-500/30 flex-row items-center justify-center gap-2 active:opacity-90"
                >
                    <Text className="text-white font-bold text-lg">등록 완료</Text>
                    <MaterialIcons name="arrow-forward" size={20} color="white" />
                </TouchableOpacity>
            </View>

            {/* Selection Modal */}
            <Modal
                visible={modalVisible}
                transparent={true}
                animationType="slide"
                onRequestClose={() => setModalVisible(false)}
            >
                <KeyboardAvoidingView
                    behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                    className="flex-1"
                >
                    <Pressable
                        className="flex-1 bg-black/60 justify-end"
                        onPress={() => setModalVisible(false)}
                    >
                        <Pressable
                            onPress={(e) => e.stopPropagation()}
                            className="bg-[#15181E] rounded-t-3xl overflow-hidden"
                            style={{
                                height: isKeyboardVisible ? '85%' : '45%',
                                maxHeight: isKeyboardVisible ? '85%' : '45%'
                            }}
                        >
                            <SafeAreaView edges={['bottom']} className="flex-1">
                                <View className="flex-row items-center justify-between p-4 border-b border-border-dark">
                                    <Text className="text-lg font-bold text-white">
                                        {activeType === 'manufacturer' ? '제조사 선택' : activeType === 'model' ? '모델명 선택' : '연식 선택'}
                                    </Text>
                                    <TouchableOpacity onPress={() => setModalVisible(false)}>
                                        <MaterialIcons name="close" size={24} color="#94a3b8" />
                                    </TouchableOpacity>
                                </View>

                                {/* Search Bar */}
                                <View className="px-4 py-3">
                                    <View className="flex-row items-center bg-[#0B0C10] border border-border-dark rounded-xl px-3 h-12">
                                        <MaterialIcons name="search" size={20} color="#94a3b8" />
                                        <TextInput
                                            value={searchQuery}
                                            onChangeText={setSearchQuery}
                                            placeholder="검색어를 입력하세요"
                                            placeholderTextColor="#64748b"
                                            className="flex-1 ml-2 text-white text-base"
                                            autoCorrect={false}
                                        />
                                        {searchQuery !== '' && (
                                            <TouchableOpacity onPress={() => setSearchQuery('')}>
                                                <MaterialIcons name="cancel" size={20} color="#64748b" />
                                            </TouchableOpacity>
                                        )}
                                    </View>
                                </View>

                                {loading ? (
                                    <View className="flex-1 items-center justify-center py-10">
                                        <ActivityIndicator size="large" color="#0d7ff2" />
                                    </View>
                                ) : (
                                    <FlatList
                                        data={filteredList}
                                        keyExtractor={(item) => item.toString()}
                                        keyboardShouldPersistTaps="handled"
                                        keyboardDismissMode="on-drag" // Dismiss keyboard on scroll
                                        className="flex-1"
                                        contentContainerStyle={{ paddingBottom: 30 }} // Add extra space at the bottom
                                        renderItem={({ item }) => (
                                            <TouchableOpacity
                                                className="p-4 border-b border-border-dark active:bg-[#1E232B]"
                                                onPress={() => handleSelect(item.toString())}
                                            >
                                                <Text className="text-base text-slate-200">
                                                    {activeType === 'year' ? `${item}년형` : item}
                                                </Text>
                                            </TouchableOpacity>
                                        )}
                                        ListEmptyComponent={
                                            <View className="items-center justify-center py-20">
                                                <Text className="text-slate-500">검색 결과가 없습니다.</Text>
                                            </View>
                                        }
                                    />
                                )}
                            </SafeAreaView>
                        </Pressable>
                    </Pressable>
                </KeyboardAvoidingView>
            </Modal>

        </View>
    );
}
