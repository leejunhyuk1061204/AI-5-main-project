import React, { useState, useEffect, useCallback, useRef } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { MaterialIcons } from '@expo/vector-icons';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import ObdConnect from '../setting/ObdConnect';
import ObdService, { ObdData } from '../services/ObdService';
import { LogBuffer } from '../services/LogBuffer';
import { useBleStore } from '../store/useBleStore';
import BaseScreen from '../components/layout/BaseScreen';

const MAX_LOG_ROWS = 2000;
// 블루투스 OBD가 수집하는 PID만 (highPids: rpm,speed,throttle + normalPids)
const CSV_HEADER = 'timestamp,rpm,speed,voltage,coolantTemp,engineLoad,fuelTrimShort,fuelTrimLong,throttle,map,maf,intakeTemp,engineRuntime';

function obdDataToCsvRow(d: ObdData): string {
    const t = d.timestamp ?? '';
    const rpm = d.rpm ?? '';
    const speed = d.speed ?? '';
    const voltage = d.voltage ?? '';
    const coolantTemp = d.coolant_temp ?? '';
    const engineLoad = d.engine_load ?? '';
    const fuelTrimShort = d.fuel_trim_short ?? '';
    const fuelTrimLong = d.fuel_trim_long ?? '';
    const throttle = d.throttle ?? '';
    const map = d.map ?? '';
    const maf = d.maf ?? '';
    const intakeTemp = d.intake_temp ?? '';
    const engineRuntime = d.engine_runtime ?? '';
    return [t, rpm, speed, voltage, coolantTemp, engineLoad, fuelTrimShort, fuelTrimLong, throttle, map, maf, intakeTemp, engineRuntime].join(',');
}

const LOG_POLL_MS = 500;

export default function Elm327TestScreen() {
    const navigation = useNavigation();
    const { status, connectedDeviceName } = useBleStore();
    const [connectModalVisible, setConnectModalVisible] = useState(false);
    const [csvRows, setCsvRows] = useState<ObdData[]>([]);
    const [latestObd, setLatestObd] = useState<ObdData | null>(null);
    const [logContent, setLogContent] = useState(() => LogBuffer.getContent());
    const [activeTab, setActiveTab] = useState<'console' | 'obd'>('console');
    const [test0302Result, setTest0302Result] = useState<{ storedDtc: string | null; freezeDtc: string | null } | null>(null);
    const [test0302Loading, setTest0302Loading] = useState(false);
    const scrollRef = useRef<ScrollView>(null);

    useEffect(() => {
        const id = setInterval(() => {
            setLogContent(LogBuffer.getContent());
        }, LOG_POLL_MS);
        return () => clearInterval(id);
    }, []);

    useEffect(() => {
        scrollRef.current?.scrollToEnd({ animated: false });
    }, [logContent]);

    const onConnected = useCallback(() => {
        setCsvRows([]);
        setLatestObd(null);
        ObdService.setManualConnectSession(true);
        ObdService.startPolling(1000);
        console.log('[Elm327Test] onConnected: log cleared, polling started');
    }, []);

    useEffect(() => {
        const unsubscribe = ObdService.onData((data: ObdData) => {
            setLatestObd(data);
            setCsvRows(prev => {
                const next = [...prev, data];
                if (next.length > MAX_LOG_ROWS) return next.slice(-MAX_LOG_ROWS);
                return next;
            });
        });
        return () => {
            unsubscribe();
            ObdService.setManualConnectSession(false);
            console.log('[Elm327Test] unmount: unsubscribed');
        };
    }, []);

    const handleDisconnect = useCallback(() => {
        console.log('[Elm327Test] disconnect tapped');
        ObdService.disconnect();
    }, []);

    const handleExportCsv = useCallback(async () => {
        const lines = [CSV_HEADER, ...csvRows.map(obdDataToCsvRow)];
        const csvString = lines.join('\n');
        const filename = `obd_test_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
        const path = `${FileSystem.documentDirectory}${filename}`;
        try {
            const encoding = (FileSystem.EncodingType && FileSystem.EncodingType.UTF8) ?? 'utf8';
            await FileSystem.writeAsStringAsync(path, csvString, { encoding });
            await Sharing.shareAsync(path);
            console.log('[Elm327Test] CSV exported rows=', csvRows.length, 'path=', path);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[Elm327Test] CSV export failed. reason=', msg);
        }
    }, [csvRows]);

    const handleExportLogFile = useCallback(async () => {
        const raw = LogBuffer.getContent();
        const content = raw.trim() === '' ? '내용 없음' : raw;
        const filename = `obd_test_log_${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
        const path = `${FileSystem.documentDirectory}${filename}`;
        try {
            const encoding = (FileSystem.EncodingType && FileSystem.EncodingType.UTF8) ?? 'utf8';
            await FileSystem.writeAsStringAsync(path, content, { encoding });
            await Sharing.shareAsync(path, { mimeType: 'application/octet-stream' });
            console.log('[Elm327Test] log file exported lines=', LogBuffer.lineCount, 'path=', path);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[Elm327Test] log file save failed. reason=', msg);
        }
    }, []);

    const handleClearConsoleLog = useCallback(() => {
        LogBuffer.clear();
        setLogContent(LogBuffer.getContent());
    }, []);

    const handleTest0302 = useCallback(async () => {
        if (status !== 'connected') return;
        setTest0302Loading(true);
        setTest0302Result(null);
        try {
            const result = await ObdService.runTest03And02();
            setTest0302Result(result);
        } finally {
            setTest0302Loading(false);
        }
    }, [status]);

    const ObdCard = ({ label, value, unit }: { label: string; value: string | number | null | undefined; unit?: string }) => (
        <View className="w-1/2 p-1">
            <View className="p-3 rounded-xl bg-black/40 border border-white/10 items-center justify-center min-h-[72px]">
                <Text className="text-[10px] text-text-muted mb-1 uppercase tracking-widest">{label}</Text>
                <Text className="text-xl font-bold text-white">
                    {value != null ? String(value) : '-'}
                </Text>
                {unit && <Text className="text-[10px] text-text-muted mt-0.5">{unit}</Text>}
            </View>
        </View>
    );

    const ObdCardGrid = ({ data }: { data: ObdData | null }) => (
        <ScrollView contentContainerStyle={{ paddingBottom: 8 }}>
            <View className="flex-row flex-wrap">
                <ObdCard label="RPM" value={data?.rpm} unit="rpm" />
                <ObdCard label="속도" value={data?.speed} unit="km/h" />
                <ObdCard label="스로틀" value={data?.throttle != null ? data.throttle.toFixed(1) : null} unit="%" />
                <ObdCard label="냉각수 온도" value={data?.coolant_temp} unit="°C" />
                <ObdCard label="엔진 부하" value={data?.engine_load != null ? data.engine_load.toFixed(1) : null} unit="%" />
                <ObdCard label="MAP" value={data?.map} unit="kPa" />
                <ObdCard label="MAF" value={data?.maf != null ? data.maf.toFixed(2) : null} unit="g/s" />
                <ObdCard label="흡기 온도" value={data?.intake_temp} unit="°C" />
                <ObdCard label="단기 연료 트림" value={data?.fuel_trim_short != null ? data.fuel_trim_short.toFixed(1) : null} unit="%" />
                <ObdCard label="장기 연료 트림" value={data?.fuel_trim_long != null ? data.fuel_trim_long.toFixed(1) : null} unit="%" />
                <ObdCard label="전압" value={data?.voltage != null ? data.voltage.toFixed(1) : null} unit="V" />
                <ObdCard label="엔진 런타임" value={data?.engine_runtime} unit="sec" />
                <ObdCard label="DTC 상태" value={data?.dtc_status} />
            </View>
            {data?.timestamp && (
                <Text className="text-[10px] text-text-muted text-center mt-2">
                    마지막 수신: {new Date(data.timestamp).toLocaleTimeString()}
                </Text>
            )}
        </ScrollView>
    );

    const connectionLabel = status === 'connected' ? `연결됨: ${connectedDeviceName || 'OBD'}` : status === 'connecting' ? '연결 중...' : '미연결';
    const totalRows = csvRows.length;

    return (
        <BaseScreen scrollable={false} padding={false} useBottomNav={false}>
            <View className="flex-1 px-4 pt-2 pb-4">
                <View className="flex-row items-center justify-between mb-3">
                    <TouchableOpacity onPress={() => navigation.goBack()} className="p-2">
                        <MaterialIcons name="arrow-back" size={24} color="#e5e7eb" />
                    </TouchableOpacity>
                    <Text className="text-lg font-semibold text-white">ELM327 테스트</Text>
                    <View style={{ width: 40 }} />
                </View>

                <View className="mb-3 flex-row items-center justify-between">
                    <Text className="text-sm text-text-muted">{connectionLabel}</Text>
                    <View className="flex-row gap-2">
                        {status === 'connected' ? (
                            <TouchableOpacity
                                onPress={handleDisconnect}
                                className="bg-red-500/20 px-3 py-1.5 rounded-lg"
                            >
                                <Text className="text-xs text-red-400 font-medium">연결 해제</Text>
                            </TouchableOpacity>
                        ) : (
                            <TouchableOpacity
                                onPress={() => setConnectModalVisible(true)}
                                className="bg-primary/80 px-3 py-1.5 rounded-lg"
                            >
                                <Text className="text-xs text-white font-medium">연결</Text>
                            </TouchableOpacity>
                        )}
                    </View>
                </View>

                <View className="flex-row gap-2 mb-2">
                    <TouchableOpacity
                        onPress={handleExportCsv}
                        className="flex-1 bg-white/10 py-2 rounded-lg items-center"
                    >
                        <Text className="text-sm text-white">CSV 내보내기 ({totalRows}행)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        onPress={handleExportLogFile}
                        className="flex-1 bg-white/10 py-2 rounded-lg items-center"
                    >
                        <Text className="text-sm text-white">로그 파일 저장 ({LogBuffer.lineCount}줄)</Text>
                    </TouchableOpacity>
                </View>
                {status === 'connected' && (
                    <View className="flex-row gap-2 mb-2">
                        <TouchableOpacity
                            onPress={handleTest0302}
                            disabled={test0302Loading}
                            className="flex-1 bg-amber-500/30 py-2 rounded-lg items-center"
                        >
                            <Text className="text-sm text-amber-200">
                                {test0302Loading ? '03/02 대기 중…' : '03/02 테스트'}
                            </Text>
                        </TouchableOpacity>
                    </View>
                )}
                {test0302Result !== null && (
                    <View className="mb-2 p-2 rounded-lg bg-black/40 border border-white/10">
                        <Text className="text-xs text-text-muted">03 (Stored): {test0302Result.storedDtc ?? 'null'}</Text>
                        <Text className="text-xs text-text-muted">02 (Freeze): {test0302Result.freezeDtc ?? 'null'}</Text>
                    </View>
                )}
                <View className="flex-row gap-2 mb-2">
                    <TouchableOpacity
                        onPress={() => setActiveTab('console')}
                        className={`flex-1 py-2 rounded-lg items-center ${activeTab === 'console' ? 'bg-primary/80' : 'bg-white/10'}`}
                    >
                        <Text className="text-sm text-white">콘솔 로그 ({LogBuffer.lineCount}줄)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        onPress={() => setActiveTab('obd')}
                        className={`flex-1 py-2 rounded-lg items-center ${activeTab === 'obd' ? 'bg-primary/80' : 'bg-white/10'}`}
                    >
                        <Text className="text-sm text-white">OBD 데이터 ({totalRows}행)</Text>
                    </TouchableOpacity>
                </View>
                {activeTab === 'console' && (
                    <View className="flex-row gap-2 mb-2">
                        <TouchableOpacity
                            onPress={handleClearConsoleLog}
                            className="bg-white/10 py-2 px-4 rounded-lg justify-center"
                        >
                            <Text className="text-sm text-white">콘솔 로그 지우기</Text>
                        </TouchableOpacity>
                    </View>
                )}
                {activeTab === 'obd' && (
                    <View className="flex-row gap-2 mb-2">
                        <TouchableOpacity
                            onPress={() => { setCsvRows([]); setLatestObd(null); }}
                            className="bg-white/10 py-2 px-4 rounded-lg justify-center"
                        >
                            <Text className="text-sm text-white">OBD 데이터 지우기</Text>
                        </TouchableOpacity>
                    </View>
                )}

                <View className="flex-1 rounded-lg bg-black/30 border border-white/10 overflow-hidden min-h-0">
                    {activeTab === 'console' ? (
                        <ScrollView
                            ref={scrollRef}
                            contentContainerStyle={{ padding: 8, paddingBottom: 16 }}
                            showsVerticalScrollIndicator={true}
                        >
                            <Text className="text-xs text-gray-300 font-mono" style={{ fontVariant: ['tabular-nums'] }}>
                                {logContent || '(로그 없음)'}
                            </Text>
                        </ScrollView>
                    ) : (
                        <ObdCardGrid data={latestObd} />
                    )}
                </View>
            </View>

            <ObdConnect
                visible={connectModalVisible}
                onClose={() => setConnectModalVisible(false)}
                onConnected={onConnected}
            />
        </BaseScreen>
    );
}
