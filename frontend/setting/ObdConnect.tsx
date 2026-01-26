import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    TouchableOpacity,
    FlatList,
    Modal,
    ActivityIndicator,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import BleService, { Peripheral } from '../services/BleService';
import ClassicBtService from '../services/ClassicBtService';
import ObdService from '../services/ObdService';
import type { BluetoothDevice } from 'react-native-bluetooth-classic';
import { useBleStore } from '../store/useBleStore';

// 통합 기기 타입 (BLE 또는 Classic)
interface UnifiedDevice {
    id: string;
    name: string;
    rssi: number;
    type: 'ble' | 'classic';
    blePeripheral?: Peripheral;
    classicDevice?: BluetoothDevice;
}

interface ObdConnectProps {
    visible: boolean;
    onClose: () => void;
    onConnected?: (device: UnifiedDevice) => void;
}

export default function ObdConnect({ visible, onClose, onConnected }: ObdConnectProps) {
    const {
        isScanning,
        status,
        scannedDevices,
        error: storeError,
        setScanning
    } = useBleStore();

    const [classicDevices, setClassicDevices] = useState<UnifiedDevice[]>([]);
    // UI Local Status (to keep 'success' modal behavior separate from just 'connected' state if needed, 
    // but we can try to rely on store. status 'connected' means success)

    // We Map store devices to UnifiedDevice for rendering
    const bleUnifiedDevices: UnifiedDevice[] = scannedDevices.map(d => ({
        id: d.id,
        name: d.name || `BLE_${d.id.substring(0, 8)}`,
        rssi: d.rssi || -100,
        type: 'ble',
        blePeripheral: d as Peripheral
    }));

    const allDevices = [...classicDevices, ...bleUnifiedDevices];

    useEffect(() => {
        BleService.initialize();
        ClassicBtService.initialize();
    }, []);

    useEffect(() => {
        if (visible) {
            // Reset UI View state if needed, but store state prevails
            setClassicDevices([]);
        }
    }, [visible]);

    // Listeners are now in BleService -> Store
    // Removed local listeners

    // 통합 스캔 (BLE + Classic)
    const startScan = async () => {
        setClassicDevices([]);

        try {
            // 1. Classic Bluetooth 페어링된 기기 가져오기
            console.log('[ObdConnect] Getting Classic BT bonded devices...');
            const classicBonded = await ClassicBtService.getBondedDevices();
            const classicList: UnifiedDevice[] = classicBonded.map(device => ({
                id: device.address,
                name: device.name || `Classic_${device.address.substring(0, 8)}`,
                rssi: -50, // Classic BT는 RSSI 제공 안 함
                type: 'classic',
                classicDevice: device,
            }));
            setClassicDevices(classicList);

            // 2. BLE 페어링된 기기 가져오기 - (BleService 내부에서 bonded 가져오는 로직은 생략하거나 store에 추가 가능, 
            // 현재 BleService store action은 스캔된 것만 추가함. 
            // bonded도 스캔 리스트에 추가하고 싶으면 여기서 수동으로 store action 호출 가능)
            // For now, let's rely on scan.

            // 3. BLE 스캔 시작 (새 기기 발견용) - This clears previous scan results in store
            await BleService.startScan();

        } catch (e) {
            console.error('[ObdConnect] Scan error:', e);
            setScanning(false);
        }
    };

    const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    // 통합 연결 함수
    const connectToDevice = async (device: UnifiedDevice, retries = 3) => {
        try {
            await BleService.stopScan();
            // Store status automatically updates to 'connecting' via BleService.connect
            // But for Classic, updating store manually in ObdService.setClassicDevice

            await delay(1000);

            console.log(`[ObdConnect] Connecting to ${device.name} (${device.type})...`);

            if (device.type === 'classic' && device.classicDevice) {
                // ===== Classic Bluetooth (SPP) 연결 =====
                const connected = await ClassicBtService.connect(device.classicDevice);

                if (connected) {
                    console.log('[ObdConnect] Classic BT connected!');
                    await ObdService.setClassicDevice(device.classicDevice);
                    // Status update is handled in ObdService

                    setTimeout(() => {
                        if (onConnected) onConnected(device);
                    }, 1500);
                } else {
                    throw new Error('Classic BT connection failed');
                }

            } else if (device.type === 'ble') { // Device ID is sufficient
                // ===== BLE 연결 =====
                await delay(500);

                // BleService.connect handles status updates via store
                await BleService.connect(device.id);

                console.log('[ObdConnect] Retrieving Services...');
                await BleService.retrieveServices(device.id);

                console.log('[ObdConnect] Configuring ObdService...');
                await ObdService.setTargetDevice(device.id);

                setTimeout(() => {
                    if (onConnected) onConnected(device);
                }, 1500);
            }

        } catch (error) {
            const msg = error instanceof Error ? error.message : JSON.stringify(error);
            console.warn(`[ObdConnect] Connection failed: ${msg}`);

            // Status will be 'disconnected' (set by BleService/ObdService on error)

            if (retries > 0) {
                console.log(`[ObdConnect] Retrying in 2 seconds...`);
                // Optionally show retry UI?
                await delay(2000);
                await connectToDevice(device, retries - 1);
            } else {
                console.error('[ObdConnect] Connection Failed:', msg);
                // Store error state is set by BleService
            }
        }
    };

    const renderItem = ({ item }: { item: UnifiedDevice }) => (
        <TouchableOpacity
            className="bg-[#ffffff08] p-4 mb-3 rounded-2xl flex-row items-center justify-between border border-[#ffffff0d] active:bg-[#ffffff10]"
            onPress={() => connectToDevice(item)}
            disabled={status === 'connecting'}
        >
            <View className="flex-row items-center gap-3">
                {/* 타입 아이콘 */}
                <View className={`w-10 h-10 rounded-full items-center justify-center ${item.type === 'classic' ? 'bg-orange-500/20' : 'bg-blue-500/20'
                    }`}>
                    <MaterialIcons
                        name={item.type === 'classic' ? 'bluetooth' : 'bluetooth-searching'}
                        size={20}
                        color={item.type === 'classic' ? '#f97316' : '#3b82f6'}
                    />
                </View>
                <View>
                    <Text className="text-white font-bold text-[15px] mb-0.5">{item.name}</Text>
                    <View className="flex-row items-center gap-2">
                        <Text className="text-slate-500 text-xs font-medium">{item.id}</Text>
                        <View className={`px-1.5 py-0.5 rounded ${item.type === 'classic' ? 'bg-orange-500/20' : 'bg-blue-500/20'
                            }`}>
                            <Text className={`text-[10px] font-bold ${item.type === 'classic' ? 'text-orange-400' : 'text-blue-400'
                                }`}>
                                {item.type === 'classic' ? 'SPP' : 'BLE'}
                            </Text>
                        </View>
                    </View>
                </View>
            </View>
            <MaterialIcons name="chevron-right" size={20} color="#52525b" />
        </TouchableOpacity>
    );

    return (
        <Modal visible={visible} animationType="slide" transparent>
            <View className="flex-1 bg-black/60 backdrop-blur-sm justify-end">
                <View className="bg-[#101922] h-[75%] rounded-t-[32px] p-6 border-t border-white/5 relative">

                    {/* Header */}
                    <View className="flex-row justify-between items-center mb-6 px-1">
                        <Text className="text-white text-xl font-bold tracking-tight">기기 연결</Text>
                        <TouchableOpacity
                            onPress={onClose}
                            className="w-8 h-8 rounded-full bg-[#ffffff08] items-center justify-center border border-[#ffffff0d]"
                        >
                            <MaterialIcons name="close" size={18} color="#a1a1aa" />
                        </TouchableOpacity>
                    </View>

                    {/* Content based on Connection Status */}
                    {status === 'connected' ? (
                        <View className="flex-1 items-center justify-center pb-20">
                            <View className="w-24 h-24 rounded-full bg-[#0d7ff2]/10 items-center justify-center mb-6 border border-[#0d7ff2]/20">
                                <MaterialIcons name="check" size={48} color="#0d7ff2" />
                            </View>
                            <Text className="text-white text-2xl font-bold mb-2">연결 성공!</Text>
                            <Text className="text-slate-400 text-center">OBD 기기와 성공적으로{'\n'}연결되었습니다.</Text>
                        </View>
                    ) : status === 'disconnected' && storeError ? (
                        <View className="flex-1 items-center justify-center pb-20">
                            <View className="w-24 h-24 rounded-full bg-red-500/10 items-center justify-center mb-6 border border-red-500/20">
                                <MaterialIcons name="error-outline" size={48} color="#ef4444" />
                            </View>
                            <Text className="text-white text-2xl font-bold mb-2">연결 실패</Text>
                            <Text className="text-slate-400 text-center mb-6">{storeError || '기기를 찾을 수 없습니다.'}</Text>
                            <TouchableOpacity
                                onPress={() => useBleStore.getState().setError(null)}
                                className="px-8 py-3 bg-[#ffffff08] rounded-full border border-white/10"
                            >
                                <Text className="text-white font-medium">다시 시도</Text>
                            </TouchableOpacity>
                        </View>
                    ) : (
                        <>
                            {/* Scanning & List UI */}
                            <TouchableOpacity
                                onPress={startScan}
                                disabled={isScanning || status === 'connecting'}
                                className="w-full mb-6 active:opacity-90"
                            >
                                <LinearGradient
                                    colors={isScanning ? ['#1e293b', '#0f172a'] : ['#0d7ff2', '#0062cc']}
                                    start={{ x: 0, y: 0 }}
                                    end={{ x: 1, y: 0 }}
                                    className={`py-4 rounded-xl items-center justify-center border ${isScanning ? 'border-slate-700' : 'border-blue-500'}`}
                                >
                                    {isScanning ? (
                                        <View className="flex-row items-center gap-2">
                                            <ActivityIndicator color="#94a3b8" size="small" />
                                            <Text className="text-slate-400 font-bold">주변 기기 검색 중...</Text>
                                        </View>
                                    ) : (
                                        <View className="flex-row items-center gap-2">
                                            <MaterialIcons name="bluetooth-searching" size={20} color="white" />
                                            <Text className="text-white font-bold text-base">기기 검색 시작</Text>
                                        </View>
                                    )}
                                </LinearGradient>
                            </TouchableOpacity>

                            {/* Type Legend */}
                            <View className="flex-row gap-4 mb-4 px-1">
                                <View className="flex-row items-center gap-1.5">
                                    <View className="w-3 h-3 rounded-full bg-orange-500" />
                                    <Text className="text-slate-400 text-xs">SPP (Classic)</Text>
                                </View>
                                <View className="flex-row items-center gap-1.5">
                                    <View className="w-3 h-3 rounded-full bg-blue-500" />
                                    <Text className="text-slate-400 text-xs">BLE (Low Energy)</Text>
                                </View>
                            </View>

                            {status === 'connecting' && (
                                <View className="absolute inset-0 z-10 bg-[#101922]/80 items-center justify-center rounded-t-[32px]">
                                    <ActivityIndicator size="large" color="#0d7ff2" />
                                    <Text className="text-white font-medium mt-4">기기에 연결 중입니다...</Text>
                                </View>
                            )}

                            <FlatList
                                data={allDevices.sort((a, b) => {
                                    // Classic 먼저, 그 다음 이름순
                                    if (a.type !== b.type) return a.type === 'classic' ? -1 : 1;
                                    return (a.name || '').localeCompare(b.name || '');
                                })}
                                renderItem={renderItem}
                                keyExtractor={(item) => item.id}
                                contentContainerStyle={{ paddingBottom: 20 }}
                                ListEmptyComponent={() => (
                                    <View className="items-center justify-center py-10 opacity-50">
                                        <MaterialIcons name="bluetooth-disabled" size={48} color="#334155" />
                                        <Text className="text-slate-500 mt-4 text-center">검색된 기기가 없습니다.{'\n'}스캔 버튼을 눌러주세요.</Text>
                                    </View>
                                )}
                            />
                        </>
                    )}
                </View>
            </View>
        </Modal>
    );
}
