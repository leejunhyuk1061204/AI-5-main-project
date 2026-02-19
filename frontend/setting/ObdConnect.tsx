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
import { useAlertStore } from '../store/useAlertStore';
import { obdDeviceApi } from '../api/obdApi';

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
    /** 연결 실패 시 호출 (모달 다시 열기 등) */
    onConnectionFailed?: () => void;
    /** 이미 연결된 상태에서 다른 차량으로 연결만 변경할 때 사용 */
    selectedVehicleId?: string | null;
    selectedVehicleLabel?: string;
    onVehicleChangeSuccess?: () => void;
}

const CONNECT_TIMEOUT_MS = 20000;

export default function ObdConnect({
    visible,
    onClose,
    onConnected,
    onConnectionFailed,
    selectedVehicleId = null,
    selectedVehicleLabel,
    onVehicleChangeSuccess
}: ObdConnectProps) {
    const {
        isScanning,
        status,
        scannedDevices,
        error: storeError,
        connectedDeviceId,
        connectedDeviceName,
        setScanning,
        setStatus,
        setError
    } = useBleStore();

    const [changingVehicle, setChangingVehicle] = useState(false);
    const [isManualConnecting, setIsManualConnecting] = useState(false);

    const [classicDevices, setClassicDevices] = useState<UnifiedDevice[]>([]);
    // UI Local Status (to keep 'success' modal behavior separate from just 'connected' state if needed, 
    // but we can try to rely on store. status 'connected' means success)

    // We Map store devices to UnifiedDevice for rendering
    // Filter out devices with no name (as requested)
    const bleUnifiedDevices: UnifiedDevice[] = scannedDevices
        .filter(d => d.name && d.name.trim().length > 0)
        .map(d => ({
            id: d.id,
            name: d.name!,
            rssi: d.rssi || -100,
            type: 'ble',
            blePeripheral: d as Peripheral
        }));

    const allDevices = React.useMemo(() => {
        const combined = [...classicDevices, ...bleUnifiedDevices];
        const seen = new Set<string>();
        return combined.filter((d) => {
            const key = `${d.type}-${d.id}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }, [classicDevices, bleUnifiedDevices]);

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

    const successAlertShown = React.useRef(false);
    const connectedDuringSessionRef = React.useRef(false);
    // 연결 성공: 이번 모달에서 막 연결에 성공한 경우에만 알림 띄우고 자동 닫기 (이미 연결된 상태에서 연 걸 때는 제외)
    useEffect(() => {
        if (status === 'connected' && visible && connectedDuringSessionRef.current) {
            if (!successAlertShown.current) {
                successAlertShown.current = true;
                useAlertStore.getState().showAlert('연결 성공', 'OBD 기기와 연결되었습니다.', 'SUCCESS');
            }
            const timer = setTimeout(() => onClose(), 1500);
            return () => clearTimeout(timer);
        }
        if (!visible) {
            successAlertShown.current = false;
            connectedDuringSessionRef.current = false;
        }
    }, [status, visible, onClose]);

    // Listeners are now in BleService -> Store
    // Removed local listeners

    // 통합 스캔 (BLE + Classic)
    const startScan = async () => {
        setClassicDevices([]);
        console.log('[ObdConnect] scan start');
        try {
            const classicBonded = await ClassicBtService.getBondedDevices();
            const classicList: UnifiedDevice[] = classicBonded
                .filter(device => device.name && device.name.trim().length > 0)
                .map(device => ({
                    id: device.address,
                    name: device.name!,
                    rssi: -50,
                    type: 'classic',
                    classicDevice: device,
                }));
            setClassicDevices(classicList);
            console.log('[ObdConnect] classic bonded count=', classicList.length);
            await BleService.startScan();
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdConnect] scan failed. reason=', msg);
            setScanning(false);
        }
    };

    const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    const timeoutMsg = `연결 시간 초과 (${CONNECT_TIMEOUT_MS / 1000}초)`;
    const connectWithTimeout = <T,>(promise: Promise<T>, ms: number, msg: string): Promise<T> =>
        Promise.race([
            promise,
            delay(ms).then(() => {
                console.warn('[ObdConnect] connect timeout fired after', ms, 'ms');
                throw new Error(msg);
            })
        ]);

    const connectToDevice = async (device: UnifiedDevice) => {
        setStatus('connecting');
        setIsManualConnecting(true);
        setError(null);
        console.log('[ObdConnect] connect start name=', device.name, 'type=', device.type, 'id=', device.id);

        // 연결 시작 즉시 모달 닫기
        onClose();

        const doConnect = async () => {
            console.log('[ObdConnect] stopScan + delay...');
            await BleService.stopScan();
            await delay(1000);

            if (device.type === 'classic' && device.classicDevice) {
                console.log('[ObdConnect] classic connect attempt...');
                const connected = await ClassicBtService.connect(device.classicDevice);

                if (connected) {
                    console.log('[ObdConnect] classic connected name=', device.name);
                    await ObdService.setClassicDevice(device.classicDevice);
                    if (onConnected) onConnected(device);
                } else {
                    throw new Error('Classic BT connection returned false');
                }

            } else if (device.type === 'ble') {
                console.log('[ObdConnect] BLE connect attempt...');
                await delay(500);
                await BleService.connect(device.id);
                await BleService.retrieveServices(device.id);
                await ObdService.setTargetDevice(device.id);
                console.log('[ObdConnect] BLE connected name=', device.name);
                if (onConnected) onConnected(device);
            }
        };

        try {
            await connectWithTimeout(doConnect(), CONNECT_TIMEOUT_MS, timeoutMsg);
            connectedDuringSessionRef.current = true;
            useAlertStore.getState().showAlert('연결 성공', `${device.name}에 연결되었습니다.`, 'SUCCESS');
        } catch (error) {
            const msg = error instanceof Error ? error.message : String(error);
            setStatus('disconnected');
            setError(msg);
            if (device.type === 'ble') {
                BleService.disconnect(device.id).catch(() => { });
            } else if (device.type === 'classic' && device.classicDevice) {
                ClassicBtService.disconnect(device.classicDevice).catch(() => { });
            }
            console.warn('[ObdConnect] manual connect failed (no retry). reason=', msg);
            useAlertStore.getState().showAlert('연결 실패', msg || '기기를 찾을 수 없습니다.', 'ERROR');
            if (onConnectionFailed) onConnectionFailed();
        } finally {
            setIsManualConnecting(false);
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
                        <View className="flex-1 pb-20">
                            {connectedDuringSessionRef.current ? (
                                <View className="flex-1 items-center justify-center">
                                    <View className="w-24 h-24 rounded-full bg-[#0d7ff2]/10 items-center justify-center mb-6 border border-[#0d7ff2]/20">
                                        <MaterialIcons name="check" size={48} color="#0d7ff2" />
                                    </View>
                                    <Text className="text-white text-2xl font-bold mb-2">연결 성공!</Text>
                                    <Text className="text-slate-400 text-center">OBD 기기와 성공적으로{'\n'}연결되었습니다.</Text>
                                </View>
                            ) : (
                                <>
                                    <View className="items-center mb-8">
                                        {!isManualConnecting && (
                                            <>
                                                <View className="w-20 h-20 rounded-full bg-[#0d7ff2]/10 items-center justify-center mb-4 border border-[#0d7ff2]/20">
                                                    <MaterialIcons name="bluetooth-connected" size={40} color="#0d7ff2" />
                                                </View>
                                                <Text className="text-white text-xl font-bold mb-1">이미 연결되어 있습니다</Text>
                                                <Text className="text-slate-400 text-center text-sm">
                                                    {connectedDeviceName || connectedDeviceId || 'OBD 기기'}와 연결 중입니다.
                                                </Text>
                                            </>
                                        )}
                                    </View>
                                    {selectedVehicleId && selectedVehicleLabel ? (
                                        <TouchableOpacity
                                            onPress={async () => {
                                                if (!connectedDeviceId) return;
                                                setChangingVehicle(true);
                                                try {
                                                    await ObdService.requestCalidCvnRefresh();
                                                    const calid = ObdService.getCalid() || undefined;
                                                    const cvn = ObdService.getCvn() || undefined;
                                                    await obdDeviceApi.recordConnect(connectedDeviceId, {
                                                        vehicleId: selectedVehicleId,
                                                        calid,
                                                        cvn
                                                    });
                                                    ObdService.setVehicleId(selectedVehicleId);
                                                    useBleStore.getState().setConnectedVehicleId(selectedVehicleId);
                                                    await ObdService.loadAndCacheDevices();
                                                    onClose();
                                                    onVehicleChangeSuccess?.();
                                                } catch (e) {
                                                    const msg = e instanceof Error ? e.message : String(e);
                                                    useAlertStore.getState().showAlert('연결 변경 실패', msg, 'ERROR');
                                                } finally {
                                                    setChangingVehicle(false);
                                                }
                                            }}
                                            disabled={changingVehicle}
                                            className="w-full py-4 bg-primary rounded-xl flex-row items-center justify-center gap-2 mb-3 border border-primary/50"
                                        >
                                            {changingVehicle ? (
                                                <ActivityIndicator size="small" color="white" />
                                            ) : (
                                                <MaterialIcons name="directions-car" size={22} color="white" />
                                            )}
                                            <Text className="text-white font-bold text-base">
                                                {changingVehicle ? '변경 중...' : `"${selectedVehicleLabel}"로 연결 변경`}
                                            </Text>
                                        </TouchableOpacity>
                                    ) : null}
                                    <Text className="text-slate-500 text-center text-xs px-4">
                                        같은 OBD를 다른 차량에 꽂았을 때, 위에서 선택한 차량으로 연결을 변경할 수 있습니다.
                                    </Text>
                                </>
                            )}
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
                                keyExtractor={(item) => `${item.type}-${item.id}`}
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
