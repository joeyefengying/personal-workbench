import React, {Component} from "react";

import {message} from "antd";

interface Props {
    shareOpens: any
    permission:boolean
    url:string
}

interface State {
    copyBtn: boolean
}

class ShareCopy extends Component<Props, State> {
    constructor(props: any) {
        super(props);
        this.state = {
            copyBtn: false
        }
    }


    public shareCopy = () => {
        const transfer = document.createElement('input')
        document.body.appendChild(transfer)
        transfer.value = this.props.url;
        transfer.select();
        document.execCommand("Copy")
        document.body.removeChild(transfer);
        if (!this.state.copyBtn) message.success('复制成功')
        this.setState({
            copyBtn: true
        })
    }

    public render() {
        return (
            <div className={'card-box'}>
                <div className={'card-left'} style={{marginTop: '5px'}}>
                    {this.props.permission?null:'分享链接 :'}
                </div>
                <div style={{width: '350px', display: 'flex'}}>
                    <input id={'inp'} className={'card-inp'} value={this.props.url} disabled />
                    <div className={'card-btn'} onClick={this.shareCopy}>
                        {this.state.copyBtn ?
                            <>
                                <img src={require('./img/tick.png')}
                                     style={{verticalAlign: 'middle', marginRight: '5px'}}/>
                                已复制
                            </>
                            : '复制链接'}
                    </div>
                </div>
            </div>
        );
    }
}

export default ShareCopy


// WEBPACK FOOTER //
// ./src/components/Share/ShareCopy.tsx