import { LocaleProvider as AntdLocaleProvider } from 'antd';
import antd_enUS from 'antd/lib/locale-provider/en_US';
import React, { Component } from 'react';
import { addLocaleData, IntlProvider } from 'react-intl';
import englishLocaleData from 'react-intl/locale-data/en';
import zhLocaleData from 'react-intl/locale-data/zh';
import { connect } from 'react-redux';
import enUS from '../../locales/en_US';
import zhCN from '../../locales/zh_CN';

addLocaleData([...zhLocaleData, ...englishLocaleData]);
// 资源文件配置
const antdLocaleConfig = {
  zh: {}, // 默认采用中文
  en: antd_enUS,
};
const localeConfig = {
  zh: zhCN,
  en: enUS,
};

interface LocaleProviderProps {
  language: string;
}

class LocaleProvider extends Component<LocaleProviderProps> {
  public render() {
    return (
      <AntdLocaleProvider locale={antdLocaleConfig[this.props.language]}>
        <IntlProvider
          key={this.props.language}
          locale={this.props.language}
          messages={localeConfig[this.props.language]}
        >
          {this.props.children}
        </IntlProvider>
      </AntdLocaleProvider>
    );
  }
}

function mapStateToProps(state: any) {
  return {
    language: state.language,
  };
}

export default connect(mapStateToProps)(LocaleProvider);



// WEBPACK FOOTER //
// ./src/containers/LocaleProvider/index.tsx