import { create } from 'zustand';

interface DatePickerState {
    isVisible: boolean;
    initialDate: Date;
    mode: 'date' | 'time' | 'datetime';
    onConfirm: ((date: Date) => void) | null;
    openDatePicker: (options: {
        initialDate?: Date;
        mode?: 'date' | 'time' | 'datetime';
        onConfirm: (date: Date) => void
    }) => void;
    closeDatePicker: () => void;
}

export const useDatePickerStore = create<DatePickerState>((set) => ({
    isVisible: false,
    initialDate: new Date(),
    mode: 'date',
    onConfirm: null,

    openDatePicker: ({ initialDate = new Date(), mode = 'date', onConfirm }) => set({
        isVisible: true,
        initialDate,
        mode,
        onConfirm
    }),

    closeDatePicker: () => set({
        isVisible: false,
        onConfirm: null
    }),
}));
