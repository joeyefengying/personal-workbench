import React, {Component} from "react";
import './index.scss'

import {Card} from "antd";
import {getQuery} from "../../utils/UrlUtil";
import ShareSelect from "./ShareSelect";
import ValidityDate from './ValidityDate'

import ShareDocuments from "./ShareDocuments";

import ShareCopy from "./ShareCopy";
import ShareLimit from "./ShareLimit";

import ShareCanvas from "./ShareCanvas";

import {GmtExpire} from "./GmtExpire";


interface Props {
    shareOpens: any;
    updateShareOpens: any;
    permission:boolean;
    url:string;
    gmtExpire:any;
    shareSwitch:boolean;
}

interface State {
    data: any;
    isb: boolean;
}


class Share extends Component<Props, State> {
    constructor(props: any) {
        super(props);
        this.state = {
            data: {},
            isb: false,
        }
    }

    public setShareOpen = () => {
        this.props.updateShareOpens()
    }

    public initData = (n: any) => {
        const arr = {
            expireType: this.props.shareOpens.expireType,
            permission: this.props.shareOpens.permission,
            resourceId: getQuery('fileId') as string,
            resourceType: 1,
            scope: this.props.shareOpens.scope
        }
        return {...arr, ...n}
    }

    public judSCope() {
        if (this.props.shareOpens && this.props.shareOpens.scope === 3) {
            return (
                <div className={'card-box'}>
                    <div className={'card-left'}>指定成员 :</div>
                    <div style={{color: '#9aa0a7'}}>网页内暂不支持选人,请在轻推内设置</div>
                </div>
            )
        } else {
            return (
                <ShareLimit
                    shareOpens={this.props.shareOpens} initData={this.initData}
                    setShareOpen={this.setShareOpen}
                />
            )
        }
    }

    public render() {
        return (
            <Card title="分享文档" bordered={true}
                  className={'ant-card-bordered'}
            >
                { this.props.shareSwitch?
                    <div>
                        <ShareDocuments
                            shareOpens={this.props.shareOpens}
                            setShareOpen={this.setShareOpen}
                        />

                        <div className={'card-noShare'}>
                            {this.props.shareOpens && this.props.shareOpens.shareOpen
                                ? null
                                : '开启后可通过链接将文件在企业内部或外部分享'}
                        </div>

                        <div style={this.props.shareOpens && this.props.shareOpens.shareOpen ? {display: 'block'} : {display: 'none'}}>
                            <ShareSelect shareOpens={this.props.shareOpens} initData={this.initData} setShareOpen={this.setShareOpen}/>
                            {this.judSCope()}
                            <ValidityDate initData={this.initData} setShareOpen={this.setShareOpen} shareOpens={this.props.shareOpens}/>
                            <GmtExpire shareOpens={this.props.shareOpens} gmtExpire={this.props.gmtExpire}/>
                            <ShareCopy shareOpens={this.props.shareOpens} permission={this.props.permission} url={this.props.url}/>
                            <ShareCanvas shareOpens={this.props.shareOpens} url={this.props.url}/>
                        </div>
                    </div>:
                    <>
                        <ShareCopy shareOpens={this.props.shareOpens} permission={this.props.permission} url={this.props.url}/>
                        <GmtExpire shareOpens={this.props.shareOpens} gmtExpire={this.props.gmtExpire}/>
                        <ShareCanvas shareOpens={this.props.shareOpens} url={this.props.url} />
                    </>
                }
            </Card>
        );
    }

}

export default Share


// WEBPACK FOOTER //
// ./src/components/Share/index.tsx