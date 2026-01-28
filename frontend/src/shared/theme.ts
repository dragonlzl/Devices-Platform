import type { ThemeConfig } from 'antd';

export const appTheme: ThemeConfig = {
  token: {
    fontFamily: "'Space Grotesk', 'Noto Sans SC', sans-serif",
    colorPrimary: '#1c7c5a',
    colorInfo: '#1c7c5a',
    colorWarning: '#b04a2c',
    colorError: '#b3261e',
    colorText: '#1b231f',
    colorTextSecondary: '#6b7570',
    borderRadius: 12,
  },
  components: {
    Button: {
      fontWeight: 600,
    },
    Table: {
      headerBg: '#e6f0ec',
    },
    Drawer: {
      paddingLG: 20,
    },
  },
};
