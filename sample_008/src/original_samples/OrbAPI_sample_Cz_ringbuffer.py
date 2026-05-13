#OrbAPI_py37.pydとOrbRecognizerCPP2.dllが必要
import numpy as np
import OrbViewAPI_py313 as orb
import csv
import time
import datetime

np.set_printoptions(legacy='1.25')

#読み出しデータ形式を0~3で切り替える
#0:指定時間分・横ベクトル読み出し、1:指定時間分・縦ベクトル読み出し、2:バッファ内全データ・横ベクトル読み出し、3:バッファ内全データ・横ベクトル読み出し
acquire_mode = 1
ch_mode = 10
#ch_mode=8,10以外で任意のチャンネルを指定する場合
#["POINT","O1","O2","C3","Cz","C4","F3","Fz","F4","A2","X1","X2"]から選択
#use_ch = ["PO8","Oz","F3"]

dt_now = datetime.datetime.now()
str_now = dt_now.strftime('%Y%m%d%H%M%S')
filepath = "./OrbAPI_test_" + str_now + ".csv"

#COMポート
COMPORT = "COM3"

def main():
    header = []
    ##通信用オブジェクトを作成
    oif = orb.OIF()

    ##チャンネル設定
    if ch_mode==8:
        ##追加電極なし
        oif.set_ch_noex()
    elif ch_mode==10:
        ##追加電極あり
        oif.set_ch_all()
    else :
        #oif.set_multi_ch_info(np.array(use_ch))
        header = ["POINT"] + use_ch + ["EXT"]
        #header = ["POINT","F4","Oz","PO7","X2","TRIG"]
        oif.set_multi_ch_info(np.array(["POINT","O1","O2","C3","Cz","C4","F3","Fz","F4","A2","X1","X2"]))


    #バッファの保持可能データ数を変更(デフォルトで5000)
    oif.change_buffer_length(7000)

    ##対応したOrbがペアリングされているCOMポートを指定
    oif.connect(COMPORT)

    oif.information()

    #インピーダンスチェック
    oif.imp_check_start()
    print("impcheck_start")
    for j in range(5):
        imp_res = oif.imp_check()
        #print(imp_res)
        if ch_mode == 10:
            print("Ref:",imp_res[0],"F3:",imp_res[1],"Fz:",imp_res[2],"F4:",imp_res[3],"C3:",imp_res[4],"Cz:",imp_res[5],"C4:",imp_res[6],"O1:",imp_res[7],"O2:",imp_res[8],"X1:",imp_res[9],"X2:",imp_res[10],"A1:",imp_res[11])
        elif ch_mode == 8:
            print("Ref:",imp_res[0],"F3:",imp_res[1],"Fz:",imp_res[2],"F4:",imp_res[3],"C3:",imp_res[4],"Cz:",imp_res[5],"C4:",imp_res[6],"O1:",imp_res[7],"O2:",imp_res[8],"A1:",imp_res[11])
    oif.imp_check_stop()

    time.sleep(2)

    ##データ転送の開始
    oif.start()
    print("start")

    #oif.inst_on(5000)

    #データ取得
    #時間ごとの行ベクトル(numpy array)として受け取る
    #[[POINT,PO7,O1,Oz,O2,PO8,F3,Fz,F4,EX1,EX2],[...],[...],...]

    if  ch_mode == 8:
        header = ["POINT","F3","Fz","F4", "C3", "Cz", "C4", "O1", "O2", "A1", "EXT"]
    elif  ch_mode == 10:
        header = ["POINT","F3","Fz","F4", "C3", "Cz", "C4", "O1", "O2", "X1", "X2","A1", "EXT"]


    with open(filepath,"w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)

    #リングバッファのTOKAI Orbからのデータ取得数/回を設定
    oif.orbtobuffer_interval(1000)

    #データ番号用
    clock_lomg = 0
    clock_short = 0

    for j in range(20):
        print("Acquiring data ... ",j)
        #このスリープが重い処理の代わり
        time.sleep(1)

        #バッファからデータの読み出し
        if acquire_mode == 0:
            #指定時間分・横ベクトル読み出し
            res = oif.getfrombuffer(1000)
        elif acquire_mode == 1:
            #指定時間分・縦ベクトル読み出し
            res = oif.getfrombuffer_trans(1000)
        elif acquire_mode == 2:
            #バッファ内全データ・横ベクトル読み出し
            res = oif.getfrombuffer_all()
        else:
            #バッファ内全データ・縦ベクトル読み出し
            res = oif.getfrombuffer_all_trans()


        #ファイルへのデータ書き込み
        with open(filepath,"a", newline='') as f:
            writer = csv.writer(f)
            if acquire_mode == 0 or acquire_mode ==  2:
                if  ch_mode == 8:
                    for i in range(len(res)):
                        this_row = [ clock_lomg + i ,  res[i][1] , res[i][2]  ,  res[i][3]  ,  res[i][4]  ,  res[i][5]  ,  res[i][6]  ,  res[i][7]  ,  res[i][8] ,  res[i][9] ,  res[i][10]  ]
                        print(this_row)
                        writer.writerow(this_row)
                        #writer.writerow( [ clock_lomg + i ,  res[i][1] , res[i][2]  ,  res[i][3]  ,  res[i][4]  ,  res[i][5]  ,  res[i][6]  ,  res[i][7]  ,  res[i][8] ,  res[i][9] ,  res[i][10]  ] )
                        clock_short += 1
                    clock_lomg += clock_short
                    clock_short = 0
                elif ch_mode == 10:
                    for i in range(len(res)):
                        this_row =[ clock_lomg + i ,  res[i][1] , res[i][2]  ,  res[i][3]  ,  res[i][4]  ,  res[i][5]  ,  res[i][6]  ,  res[i][7]  ,  res[i][8] ,  res[i][9] ,  res[i][10] ,  res[i][11],  res[i][12]  ]
                        print(this_row)
                        writer.writerow(this_row)
                        #writer.writerow( [ clock_lomg + i ,  res[i][1] , res[i][2]  ,  res[i][3]  ,  res[i][4]  ,  res[i][5]  ,  res[i][6]  ,  res[i][7]  ,  res[i][8] ,  res[i][9] ,  res[i][10],  res[i][11] ,  res[i][12]  ] )
                        clock_short += 1
                    clock_lomg += clock_short
                    clock_short = 0
            elif acquire_mode == 1 or acquire_mode == 3:
                if ch_mode == 8:
                    for i in range(len(res[0])):
                        this_row = [ clock_lomg + i ,  res[1][i] , res[2][i]  ,  res[3][i]  ,  res[4][i]  ,  res[5][i]  ,  res[6][i]  ,  res[7][i]  ,  res[8][i] ,  res[9][i] ,  res[10][i]  ]
                        print(this_row)
                        writer.writerow(this_row)
                        #writer.writerow( [ clock_lomg + i ,  res[1][i] , res[2][i]  ,  res[3][i]  ,  res[4][i]  ,  res[5][i]  ,  res[6][i]  ,  res[7][i]  ,  res[8][i] ,  res[9][i] ,  res[10][i] ] )
                        clock_short += 1
                    clock_lomg += clock_short
                    clock_short = 0
                elif ch_mode == 10:
                    for i in range(len(res[0])):
                        this_row = [ clock_lomg + i ,  res[1][i] , res[2][i]  ,  res[3][i]  ,  res[4][i]  ,  res[5][i]  ,  res[6][i]  ,  res[7][i]  ,  res[8][i] ,  res[9][i] ,  res[10][i] ,  res[11][i] ,  res[12][i] ]
                        print(this_row)
                        writer.writerow(this_row)
                        #writer.writerow( [ clock_lomg + i ,  res[1][i] , res[2][i]  ,  res[3][i]  ,  res[4][i]  ,  res[5][i]  ,  res[6][i]  ,  res[7][i]  ,  res[8][i] ,  res[9][i] ,  res[10][i] ,  res[11][i] ,  res[12][i] ] )
                        clock_short += 1
                    clock_lomg += clock_short
                    clock_short = 0
                else :
                    #使用するチャンネル数に応じて適宜ファイル書き込みを行ってください

                    for i in range(len(res[0])):
                        writer.writerow( [ clock_lomg + i ,  res[1][i] , res[2][i]  ,  res[3][i]  ,  res[4][i]  , res[5][i] ] )
                        clock_short += 1
                    clock_lomg += clock_short
                    clock_short = 0


    #バッファのリングバッファのTOKAI Orbからのデータ取得を停止.
    oif.orbtobuffer_stopinterval()

    #終了処理
    oif.end()
    oif.disconnect()
    print("end")
    del oif



if __name__ == '__main__':
    main()
