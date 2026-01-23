import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, TextInput, Alert, Modal, KeyboardAvoidingView, Platform, Keyboard, TouchableWithoutFeedback } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authService, UserResponse } from '../services/auth';
import { CommonActions } from '@react-navigation/native';

export default function MyPage() {
    const navigation = useNavigation<any>();
    const [user, setUser] = useState<UserResponse | null>(null);
    const [loading, setLoading] = useState(true);
    // Modal State
    const [modalVisible, setModalVisible] = useState(false);
    const [modalType, setModalType] = useState<'nickname' | 'password' | 'delete' | 'alert' | 'none'>('none');
    const [tempInput, setTempInput] = useState('');

    // Alert State
    const [alertConfig, setAlertConfig] = useState({ title: '', message: '', onConfirm: () => { } });

    useEffect(() => {
        fetchUserProfile();
    }, []);

    const fetchUserProfile = async () => {
        try {
            const token = await AsyncStorage.getItem('accessToken');
            if (!token) {
                navigation.navigate('Login');
                return;
            }
            const response = await authService.getProfile(token);
            if (response.success && response.data) {
                setUser(response.data);
                await AsyncStorage.setItem('userNickname', response.data.nickname);
            }
        } catch (error) {
            console.error('Failed to fetch profile', error);
        } finally {
            setLoading(false);
        }
    };

    // Custom Alert Helper
    const showAlert = (title: string, message: string, onConfirm?: () => void) => {
        setAlertConfig({
            title,
            message,
            onConfirm: onConfirm || (() => setModalVisible(false))
        });
        setModalType('alert');
        setModalVisible(true);
    };

    // Action Handlers
    const openNicknameModal = () => {
        if (user) {
            setTempInput(user.nickname); // Pre-fill current nickname
            setModalType('nickname');
            setModalVisible(true);
        }
    };

    const openPasswordModal = () => {
        setTempInput('');
        setModalType('password');
        setModalVisible(true);
    };

    const openDeleteModal = () => {
        setModalType('delete');
        setModalVisible(true);
    };

    // Confirm Logic
    const handleConfirm = async () => {
        if (modalType === 'nickname') {
            if (!tempInput || tempInput.length < 2) {
                showAlert('오류', '닉네임은 2글자 이상이어야 합니다.', () => setModalType('nickname'));
                return;
            }
            try {
                const token = await AsyncStorage.getItem('accessToken');
                if (token) {
                    const res = await authService.updateProfile(token, tempInput);
                    if (res.success) {
                        setModalVisible(false);
                        setTimeout(() => {
                            showAlert('성공', '닉네임이 성공적으로 변경되었습니다.', () => {
                                setModalVisible(false);
                                fetchUserProfile();
                            });
                        }, 300);
                    } else {
                        showAlert('실패', res.error?.message || '닉네임 변경 실패', () => setModalType('nickname'));
                    }
                }
            } catch (e) {
                showAlert('오류', '통신 중 오류가 발생했습니다.');
                console.error(e);
            }
        } else if (modalType === 'password') {
            if (!tempInput || tempInput.length < 6) {
                showAlert('오류', '비밀번호는 6자리 이상이어야 합니다.', () => setModalType('password'));
                return;
            }
            try {
                const token = await AsyncStorage.getItem('accessToken');
                if (token) {
                    const res = await authService.updateProfile(token, undefined, tempInput);
                    if (res.success) {
                        setModalVisible(false);
                        setTimeout(() => {
                            showAlert('성공', '비밀번호가 변경되었습니다.\n다시 로그인해주세요.', async () => {
                                setModalVisible(false);
                                await AsyncStorage.clear();
                                navigation.dispatch(
                                    CommonActions.reset({
                                        index: 0,
                                        routes: [{ name: 'Login' }],
                                    })
                                );
                            });
                        }, 300);
                    } else {
                        showAlert('실패', res.error?.message || '비밀번호 변경 실패', () => setModalType('password'));
                    }
                }
            } catch (e) {
                showAlert('오류', '통신 중 오류가 발생했습니다.');
            }
        } else if (modalType === 'delete') {
            try {
                const token = await AsyncStorage.getItem('accessToken');
                if (token) {
                    const res = await authService.deleteAccount(token);
                    if (res.success) {
                        setModalVisible(false);
                        setTimeout(() => {
                            showAlert('완료', '회원 탈퇴가 처리되었습니다.', async () => {
                                setModalVisible(false);
                                await AsyncStorage.clear();
                                navigation.dispatch(
                                    CommonActions.reset({
                                        index: 0,
                                        routes: [{ name: 'Login' }],
                                    })
                                );
                            });
                        }, 300);
                    } else {
                        showAlert('실패', res.error?.message || '탈퇴 실패');
                    }
                }
            } catch (e) {
                showAlert('오류', '통신 중 오류가 발생했습니다.');
                console.error(e);
            }
        } else if (modalType === 'alert') {
            alertConfig.onConfirm();
        }
    };

    const SettingItem = ({ icon, label, value, onPress, isDestructive = false }: { icon: keyof typeof MaterialIcons.glyphMap, label: string, value?: string, onPress?: () => void, isDestructive?: boolean }) => (
        <TouchableOpacity
            className={`flex-row items-center justify-between p-4 bg-[#17212b] rounded-xl border ${isDestructive ? 'border-red-500/10 active:bg-red-500/10' : 'border-white/5 active:bg-white/5'} mb-3`}
            activeOpacity={0.7}
            onPress={onPress}
        >
            <View className="flex-row items-center gap-4">
                <View className={`w-10 h-10 rounded-lg items-center justify-center ${isDestructive ? 'bg-red-500/10' : 'bg-primary/10'}`}>
                    <MaterialIcons
                        name={icon}
                        size={20}
                        color={isDestructive ? '#ef4444' : (icon === 'stars' ? '#c5a059' : '#0d7ff2')}
                    />
                </View>
                <View>
                    <Text className={`text-[10px] font-bold uppercase tracking-wider mb-0.5 ${isDestructive ? 'text-red-500' : 'text-gray-500'}`}>
                        {label}
                    </Text>
                    {value && <Text className={`text-[15px] font-medium ${isDestructive ? 'text-red-500' : 'text-white'}`}>{value}</Text>}
                </View>
            </View>
            <MaterialIcons name="chevron-right" size={20} color={isDestructive ? '#fca5a5' : '#6b7280'} />
        </TouchableOpacity>
    );

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <SafeAreaView className="z-10 bg-background-dark/90 sticky top-0 border-b border-white/5" edges={['top']}>
                <View className="flex-row items-center justify-between px-4 py-3">
                    <TouchableOpacity
                        className="w-10 h-10 items-center justify-center"
                        onPress={() => navigation.goBack()}
                    >
                        <MaterialIcons name="arrow-back-ios-new" size={24} color="#0d7ff2" />
                    </TouchableOpacity>
                    <Text className="text-white text-lg font-bold flex-1 text-center pr-10">내 프로필 및 계정 설정</Text>
                </View>
            </SafeAreaView>

            <ScrollView className="flex-1 px-5 pt-6" contentContainerStyle={{ paddingBottom: 50 }}>
                {/* Profile Card */}
                <LinearGradient
                    colors={['#1a2a3a', '#111a24']}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    className="p-8 rounded-2xl border border-white/5 relative overflow-hidden mb-8 items-center"
                >
                    <View className="absolute -right-4 -top-4 w-24 h-24 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

                    <View className="px-2 py-0.5 rounded-full bg-[#c5a059]/20 border border-[#c5a059]/30 mb-3">
                        <Text className="text-[#c5a059] text-[10px] font-bold uppercase tracking-wider">PREMIUM</Text>
                    </View>

                    <Text className="text-white text-2xl font-bold tracking-tight mb-1">
                        {user?.nickname || '사용자'}
                    </Text>
                    <Text className="text-gray-400 text-sm">
                        {user?.email || 'user@example.com'}
                    </Text>
                </LinearGradient>

                {/* Account Management */}
                <Text className="text-gray-500 text-xs font-bold uppercase tracking-[0.1em] mb-3 px-1">계정 관리</Text>

                <SettingItem
                    icon="stars"
                    label="멤버십 등급"
                    value="프리미엄 멤버십"
                    onPress={() => navigation.navigate('Membership')}
                />

                <SettingItem
                    icon="edit"
                    label="닉네임 수정"
                    value="닉네임 변경하기"
                    onPress={openNicknameModal}
                />

                <SettingItem
                    icon="lock-reset"
                    label="비밀번호 변경"
                    value="비밀번호 재설정"
                    onPress={openPasswordModal}
                />

                <View className="h-4" />

                <SettingItem
                    icon="person-remove"
                    label="서비스 탈퇴"
                    value="계정 삭제"
                    isDestructive
                    onPress={openDeleteModal}
                />

                {/* Footer */}
                <View className="mt-10 items-center opacity-30">
                    <View className="w-12 h-12 bg-primary rounded-xl mb-3 items-center justify-center">
                        <MaterialIcons name="settings-suggest" size={30} color="white" />
                    </View>
                    <Text className="text-[10px] text-white font-bold uppercase tracking-widest">Predictive AI Maintenance v2.4</Text>
                </View>
            </ScrollView>

            {/* Custom Unified Modal */}
            <Modal
                animationType="fade"
                transparent={true}
                visible={modalVisible}
                onRequestClose={() => setModalVisible(false)}
            >
                <TouchableWithoutFeedback onPress={() => Keyboard.dismiss()}>
                    <KeyboardAvoidingView
                        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                        className="flex-1 justify-center items-center bg-black/80 px-6"
                    >
                        <View className="w-full bg-[#17212b] rounded-2xl border border-white/10 p-6 shadow-2xl">
                            {/* Modal Content Switch */}
                            {/* Alert Type */}
                            {modalType === 'alert' && (
                                <View className="items-center mb-6">
                                    <View className="w-12 h-12 rounded-full bg-primary/10 items-center justify-center mb-3">
                                        <MaterialIcons name="info" size={24} color="#0d7ff2" />
                                    </View>
                                    <Text className="text-white text-lg font-bold mb-2">{alertConfig.title}</Text>
                                    <Text className="text-gray-400 text-sm text-center leading-relaxed">
                                        {alertConfig.message}
                                    </Text>
                                </View>
                            )}

                            {modalType === 'nickname' && (
                                <>
                                    <View className="items-center mb-4">
                                        <View className="w-12 h-12 rounded-full bg-primary/10 items-center justify-center mb-3">
                                            <MaterialIcons name="edit" size={24} color="#0d7ff2" />
                                        </View>
                                        <Text className="text-white text-lg font-bold">닉네임 수정</Text>
                                        <Text className="text-gray-400 text-sm text-center mt-1">새로운 닉네임을 입력해주세요.</Text>
                                    </View>
                                    <TextInput
                                        value={tempInput}
                                        onChangeText={setTempInput}
                                        className="w-full bg-black/30 text-white rounded-xl px-4 py-3 border border-white/10 mb-6"
                                        placeholder="닉네임 입력 (2글자 이상)"
                                        placeholderTextColor="#6b7280"
                                        autoFocus
                                    />
                                </>
                            )}

                            {modalType === 'password' && (
                                <>
                                    <View className="items-center mb-4">
                                        <View className="w-12 h-12 rounded-full bg-orange-500/10 items-center justify-center mb-3">
                                            <MaterialIcons name="lock-reset" size={24} color="#f97316" />
                                        </View>
                                        <Text className="text-white text-lg font-bold">비밀번호 변경</Text>
                                        <Text className="text-gray-400 text-sm text-center mt-1">새로운 비밀번호를 입력해주세요.</Text>
                                    </View>
                                    <TextInput
                                        value={tempInput}
                                        onChangeText={setTempInput}
                                        className="w-full bg-black/30 text-white rounded-xl px-4 py-3 border border-white/10 mb-6"
                                        placeholder="새 비밀번호 입력 (6자리 이상)"
                                        placeholderTextColor="#6b7280"
                                        secureTextEntry
                                        autoFocus
                                    />
                                </>
                            )}

                            {modalType === 'delete' && (
                                <View className="items-center mb-6">
                                    <View className="w-12 h-12 rounded-full bg-red-500/10 items-center justify-center mb-3">
                                        <MaterialIcons name="warning" size={24} color="#ef4444" />
                                    </View>
                                    <Text className="text-red-500 text-lg font-bold">서비스 탈퇴</Text>
                                    <Text className="text-gray-400 text-sm text-center mt-2 leading-relaxed">
                                        정말로 탈퇴하시겠습니까?{'\n'}계정 정보는 영구적으로 삭제되며{'\n'}복구할 수 없습니다.
                                    </Text>
                                </View>
                            )}

                            {/* Buttons */}
                            <View className="flex-row gap-3">
                                {modalType !== 'alert' && (
                                    <TouchableOpacity
                                        className="flex-1 py-3.5 rounded-xl bg-white/5 items-center active:bg-white/10"
                                        onPress={() => setModalVisible(false)}
                                    >
                                        <Text className="text-gray-300 font-semibold">취소</Text>
                                    </TouchableOpacity>
                                )}

                                <TouchableOpacity
                                    className={`flex-1 py-3.5 rounded-xl items-center ${modalType === 'delete' ? 'bg-red-500/10 border border-red-500/20 active:bg-red-500/20' : 'bg-primary active:bg-blue-600'}`}
                                    onPress={handleConfirm}
                                >
                                    <Text className={`font-semibold ${modalType === 'delete' ? 'text-red-500' : 'text-white'}`}>
                                        {modalType === 'delete' ? '탈퇴하기' : (modalType === 'alert' ? '확인' : '변경 완료')}
                                    </Text>
                                </TouchableOpacity>
                            </View>
                        </View>
                    </KeyboardAvoidingView>
                </TouchableWithoutFeedback>
            </Modal>
        </View>
    );
}
