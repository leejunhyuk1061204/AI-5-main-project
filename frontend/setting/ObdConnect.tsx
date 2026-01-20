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
import { BluetoothDevice } from 'react-native-bluetooth-classic';

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
    const [isScanning, setIsScanning] = useState(false);
    const [devices, setDevices] = useState<Map<string, UnifiedDevice>>(new Map());
    const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'success' | 'error'>('idle');
    const [errorMessage, setErrorMessage] = useState('');

    useEffect(() => {
        BleService.initialize();
        ClassicBtService.initialize();
    }, []);

    useEffect(() => {
        if (visible) {
            setConnectionStatus('idle');
            setErrorMessage('');
            setDevices(new Map());
        }
    }, [visible]);

    useEffect(() => {
        const discoverListener = BleService.addListener(
            'BleManagerDiscoverPeripheral',
            handleDiscoverBlePeripheral
        );
        const stopScanListener = BleService.addListener(
            'BleManagerStopScan',
            handleStopScan
        );

        return () => {
            discoverListener.remove();
            stopScanListener.remove();
        };
    }, []);

    // BLE 기기 발견 핸들러
    const handleDiscoverBlePeripheral = (peripheral: Peripheral) => {
        const localName = peripheral.advertising?.localName || peripheral.advertising?.kCBAdvDataLocalName;
        const deviceName = peripheral.name || localName || `BLE_${peripheral.id.substring(0, 8)}`;

        const unifiedDevice: UnifiedDevice = {
            id: peripheral.id,
            name: deviceName,
            rssi: peripheral.rssi || -100,
            type: 'ble',
            blePeripheral: { ...peripheral, name: deviceName },
        };

        setDevices((map) => new Map(map.set(peripheral.id, unifiedDevice)));
    };

    const handleStopScan = () => {
        setIsScanning(false);
    };

    // 통합 스캔 (BLE + Classic)
    const startScan = async () => {
        setConnectionStatus('idle');
        setErrorMessage('');
        setDevices(new Map());
        setIsScanning(true);

        try {
            const deviceMap = new Map<string, UnifiedDevice>();

            // 1. Classic Bluetooth 페어링된 기기 가져오기
            console.log('[ObdConnect] Getting Classic BT bonded devices...');
            const classicBonded = await ClassicBtService.getBondedDevices();
            classicBonded.forEach((device) => {
                const unified: UnifiedDevice = {
                    id: device.address,
                    name: device.name || `Classic_${device.address.substring(0, 8)}`,
                    rssi: -50, // Classic BT는 RSSI 제공 안 함
                    type: 'classic',
                    classicDevice: device,
                };
                deviceMap.set(device.address, unified);
                console.log(`[ObdConnect] Classic device: ${unified.name} (${device.address})`);
            });

            // 2. BLE 페어링된 기기 가져오기
            console.log('[ObdConnect] Getting BLE bonded devices...');
            const bleBonded = await BleService.getBondedPeripherals();
            bleBonded.forEach((p) => {
                // Classic과 중복되지 않으면 추가
                if (!deviceMap.has(p.id)) {
                    const unified: UnifiedDevice = {
                        id: p.id,
                        name: p.name || `BLE_${p.id.substring(0, 8)}`,
                        rssi: p.rssi || -100,
                        type: 'ble',
                        blePeripheral: p,
                    };
                    deviceMap.set(p.id, unified);
                }
            });

            setDevices(deviceMap);
            console.log(`[ObdConnect] Total devices found: ${deviceMap.size}`);

            // 3. BLE 스캔 시작 (새 기기 발견용)
            await BleService.startScan();

        } catch (e) {
            console.error('[ObdConnect] Scan error:', e);
            setIsScanning(false);
        }
    };

    const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    // 통합 연결 함수
    const connectToDevice = async (device: UnifiedDevice, retries = 3) => {
        try {
            await BleService.stopScan();
            setIsScanning(false);
            setConnectionStatus('connecting');
            await delay(1000);

            console.log(`[ObdConnect] Connecting to ${device.name} (${device.type})...`);

            if (device.type === 'classic' && device.classicDevice) {
                // ===== Classic Bluetooth (SPP) 연결 =====
                const connected = await ClassicBtService.connect(device.classicDevice);

                if (connected) {
                    console.log('[ObdConnect] Classic BT connected!');

                    // ObdService에 Classic BT 기기 설정 (OBD 데이터 수집 준비)
                    console.log('[ObdConnect] Configuring ObdService for Classic BT...');
                    await ObdService.setClassicDevice(device.classicDevice);

                    setConnectionStatus('success');

                    setTimeout(() => {
                        if (onConnected) onConnected(device);
                    }, 1500);
                } else {
                    throw new Error('Classic BT connection failed');
                }

            } else if (device.type === 'ble' && device.blePeripheral) {
                // ===== BLE 연결 =====
                await delay(500);

                const isConnected = await BleService.isPeripheralConnected(device.id, []);

                if (!isConnected) {
                    try {
                        await BleService.disconnect(device.id);
                        await delay(500);
                    } catch (e) {
                        // Ignore
                    }

                    await BleService.connect(device.id);
                    await delay(2000);
                }

                console.log('[ObdConnect] Retrieving Services...');
                await BleService.retrieveServices(device.id);

                console.log('[ObdConnect] Configuring ObdService...');
                await ObdService.setTargetDevice(device.id);

                setConnectionStatus('success');

                setTimeout(() => {
                    if (onConnected) onConnected(device);
                }, 1500);
            }

        } catch (error) {
            const msg = error instanceof Error ? error.message : JSON.stringify(error);
            console.warn(`[ObdConnect] Connection failed: ${msg}`);

            // BLE 연결 실패 시 removeBond 시도
            if (device.type === 'ble') {
                try {
                    if (msg.includes('Device disconnected') || msg.includes('status 133')) {
                        console.log('[ObdConnect] Attempting to remove stale bond (3s timeout)...');
                        const removeBondWithTimeout = Promise.race([
                            BleService.removeBond(device.id),
                            new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 3000))
                        ]);
                        await removeBondWithTimeout;
                        await delay(500);
                    }
                } catch (e) {
                    console.warn('[ObdConnect] Remove bond skipped/failed:', e);
                }
            }

            if (retries > 0) {
                console.log(`[ObdConnect] Retrying in 2 seconds...`);
                setErrorMessage(`연결 재시도 중... (${retries})`);
                await delay(2000);
                await connectToDevice(device, retries - 1);
            } else {
                setConnectionStatus('error');
                console.error('[ObdConnect] Connection Failed:', msg);
                setErrorMessage(`연결 실패: ${msg}\n\n[해결법]\n1. 안드로이드 설정 > 블루투스에서 기기 등록 해제(Unpair)\n2. 다시 페어링 후 재시도`);
            }
        }
    };

    const renderItem = ({ item }: { item: UnifiedDevice }) => (
        <TouchableOpacity
            className="bg-[#ffffff08] p-4 mb-3 rounded-2xl flex-row items-center justify-between border border-[#ffffff0d] active:bg-[#ffffff10]"
            onPress={() => connectToDevice(item)}
            disabled={connectionStatus === 'connecting'}
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
                    {connectionStatus === 'success' ? (
                        <View className="flex-1 items-center justify-center pb-20">
                            <View className="w-24 h-24 rounded-full bg-[#0d7ff2]/10 items-center justify-center mb-6 border border-[#0d7ff2]/20">
                                <MaterialIcons name="check" size={48} color="#0d7ff2" />
                            </View>
                            <Text className="text-white text-2xl font-bold mb-2">연결 성공!</Text>
                            <Text className="text-slate-400 text-center">OBD 기기와 성공적으로{'\n'}연결되었습니다.</Text>
                        </View>
                    ) : connectionStatus === 'error' ? (
                        <View className="flex-1 items-center justify-center pb-20">
                            <View className="w-24 h-24 rounded-full bg-red-500/10 items-center justify-center mb-6 border border-red-500/20">
                                <MaterialIcons name="error-outline" size={48} color="#ef4444" />
                            </View>
                            <Text className="text-white text-2xl font-bold mb-2">연결 실패</Text>
                            <Text className="text-slate-400 text-center mb-6">{errorMessage || '기기를 찾을 수 없습니다.'}</Text>
                            <TouchableOpacity
                                onPress={() => setConnectionStatus('idle')}
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
                                disabled={isScanning || connectionStatus === 'connecting'}
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

                            {connectionStatus === 'connecting' && (
                                <View className="absolute inset-0 z-10 bg-[#101922]/80 items-center justify-center rounded-t-[32px]">
                                    <ActivityIndicator size="large" color="#0d7ff2" />
                                    <Text className="text-white font-medium mt-4">기기에 연결 중입니다...</Text>
                                </View>
                            )}

                            <FlatList
                                data={Array.from(devices.values()).sort((a, b) => {
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
