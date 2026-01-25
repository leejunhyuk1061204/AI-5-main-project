import React from 'react';
import DateTimePickerModal from "react-native-modal-datetime-picker";
import { useDatePickerStore } from '../../store/useDatePickerStore';

const GlobalDatePicker = () => {
    const { isVisible, initialDate, mode, onConfirm, closeDatePicker } = useDatePickerStore();

    const handleConfirm = (date: Date) => {
        if (onConfirm) {
            onConfirm(date);
        }
        closeDatePicker();
    };

    return (
        <DateTimePickerModal
            isVisible={isVisible}
            mode={mode}
            date={initialDate}
            onConfirm={handleConfirm}
            onCancel={closeDatePicker}
            headerTextIOS="날짜 선택"
            confirmTextIOS="확인"
            cancelTextIOS="취소"
            textColor="black"
        />
    );
};

export default GlobalDatePicker;
