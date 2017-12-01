#coding:utf-8
from __future__ import division

import os
import sys
import readline
import time

import yaml
import re

import tab
import platform

import threading

import config

import data
import ssh
import sftp
import common
import threads_func

symtem_name = platform.system()

sshpass = config.sshpass
source_path = config.source_path
yaml_path = config.yaml_path

regex = re.compile(r'([\s\S]+?)-\d+$')#正则匹配 名字 关联批量操作
regex_cmd = re.compile(r'^(\d+):([\w\W]+)')#多台服务器操作时 判断是否只操作一台

ssh_login_cmd = re.compile(r'^(\d+) ([\w\W]{2,})')#多台服务器操作时 判断是否只操作一台

reload(sys)
sys.setdefaultencoding( "utf-8" )
COMMANDS = ['cmd ','quit','help']
def complete(text, state):

    for cmd in COMMANDS:
        if cmd.startswith(text):
            if not state:
                return cmd
            else:
                state -= 1

def complete_path(text, state):#自动补全
    global ssh_complete,path_complete
    cmd = 'cd '+path_complete+' && ls -F'
    path =''
    if '/' in text:
        path = text[0:text.rindex('/')] +'/'
        sub_text = text[text.rindex('/')+1:]
        cmd = 'cd '+path_complete+' && cd ' + path +' && ls -F'
    else:
        sub_text = text
    temp = ssh.cmd_cache( ssh_complete, cmd)
    temp_list_file = temp.split('\n')
    list_file = list()
    for line in temp_list_file:
        if(line[-1] == '#' or line[-1]=='*' or line[-1]=='=' or line[-1]=='|' or line[-1]=='@'):
            list_file.append(line[0:-1])
        else:
            list_file.append(line)

    for file_name in list_file:
        if file_name.startswith(sub_text):
            if not state:
                return path+file_name
            else:
                state -= 1


def check_up(server_num,sftp_conns,localPath,remotePath,fileName,cmdPath,n):
    if( os.path.isdir( localPath ) ):
        os.chdir(os.path.split(localPath)[0])
        cmd = 'find ' + localPath + ' -type f | wc -l'
        for line in os.popen(cmd):
            file_num = int(line) 
        if( file_num > 15):
            # input_result = raw_input( '上传文件数量为:%d,建议压缩后再上传(输入y继续上传,输入t打包下载,输入n退出):' %file_num )
            input_result = 't'
            if( input_result == 'y'):
                sftp.up_files(sftp_conns,localPath,remotePath )
            elif( input_result == 't'):
                global new_time
                new_time = str( new_time )

                if ( n != 0 ):
                    print '开始上传 %s_%s.tar.gz '  %(fileName,new_time )
                else:
                    cmd = 'tar -czf %s_%s.tar.gz %s' %( fileName,new_time , fileName)
                    os.system( cmd )    
                    print '打包完成,开始上传 %s_%s.tar.gz '  %(fileName,new_time )
                sftp.upload(server_num,localPath+'_'+new_time+'.tar.gz',remotePath + fileName+'_'+new_time+'.tar.gz')

                # input_result2 = raw_input( '上传完成,是否解压(y/n):' )
                input_result2 = 'y'

                if( input_result2 == 'y'):

                    cmd = 'tar -xvf %s_%s.tar.gz'  %( fileName,new_time) 
                    print( cmd )
                    result = ssh.cmd(server_num,'cd '+cmdPath+' && '+ cmd)

                    cmd= 'rm %s_%s.tar.gz' %( fileName,new_time)
                    print( cmd )
                    result = ssh.cmd(server_num,'cd '+cmdPath+' && '+ cmd)
                else:
                    return
            else:
                return
        else:
            sftp.up_files(sftp_conns,localPath,remotePath )
    
    else:
        sftp.upload(server_num,localPath,remotePath + fileName)




    
def check_down( server_num,remotePath,localPath,fileName ,cmdPath):#检查下载
    scp = data.scp_conns[ server_num ]
    try:
        scp.listdir_attr(remotePath)
    except Exception,e:
        sftp.down(server_num,remotePath,localPath+fileName)
        return 'ok'
    try:
        cmd = 'find ' + remotePath + ' -type f | wc -l'
        file_num = int( ssh.cmd(server_num,cmd) )
        if( file_num >15 ):
            global new_time
            new_time = str( new_time )
            input_result = raw_input( '下载文件数量为:%d,建议压缩后再下载(输入y继续下载,输入t打包下载,输入n退出):' %file_num )
            if(input_result == 'y'):
                sftp.downs(server_num,remotePath,localPath)
            elif(input_result == 't'):
                if fileName == '':
                    temp=remotePath.split('/')
                    fileName = temp[ len(temp)-2]
                cmd = 'tar -czf %s_%s.tar.gz %s' %( fileName, new_time , fileName)
                print( cmd )
                cmd = 'cd '+cmdPath+' && '+ cmd
                cmd_result = ssh.cmd(server_num,cmd)

                if( cmd_result == '' ):
                    print( '打包完成,开始下载 %s_%s.tar.gz '  %(fileName ,new_time) )
                    sftp.down(server_num,cmdPath + '/'+ fileName + '_'+new_time+ '.tar.gz',localPath+fileName+'_'+new_time+'.tar.gz')

                else:
                    print '操作失败'
            elif(input_result == 'n'):
                return 'n'
            else:
                return 'n'
        else:
            sftp.downs(server_num,remotePath,localPath)
    except Exception,e:
        print e
        return 'n'
    return 'ok'



def relation_add( l ,i ,sign):
    global relation 
    result_str =''
    
    if( regex.match( l['name'] ) != None ):
        relation_key = regex.match( l['name'] ).group(1)

        if( len(sys.argv) >1 and sys.argv[1] == 'all' ):
            result_str = sign+'\33[41m%s\33[0m:%s(%s)\n' %(i, l['name'],common.hideip_fun(l['host']) )
        else:
            if( not relation.has_key( relation_key  ) ):
                result_str = sign+'\33[41m%s\33[0m:%s(%s) <<%s>>\n' %(i, l['name'],common.hideip_fun(l['host']) ,relation_key )
        
        if( not relation.has_key( relation_key  ) ):

            relation[ relation_key ] = list()
            

        relation[ relation_key ].append(i) 


        return result_str
    else:
        return sign+'%s:%s(%s)\n' %(i, l['name'],common.hideip_fun(l['host'])) 

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass

    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass

    return False
def list_del_empty(data):
    while '' in data:
        data.remove('')
    return data

def ssh_cmd_func(server_num,result,p_cmd,ssh_conns,source_path,n):
    global cmds
    server_num = int(server_num)
    server_info = result[ server_num ]

    print ('\33[34m%d:\33[31m%s(%s)\33[0m' %(server_num,server_info['name'],common.hideip_fun(server_info['host']) ) )

    cmd = p_cmd

    if( p_cmd[0:2] == 'cd'):
        cmd = 'cd '+data.paths[server_num]+' && '+ cmd
        temp_path = ssh.cd(server_num,cmd )
        if( temp_path ):
            data.paths[server_num] = temp_path 
        else:
            return 'notpath'

    elif( p_cmd[0:2] ==  'up' ):
        cmds = cmd.split(' ')
        if cmds[1][len(cmds[1])-1] == '/':
            cmds[1] = cmds[1][0:len(cmds[1])-1]
        fileName = cmds[1].split('/')

        check_up(server_num, data.scp_conns[ server_num ],source_path+'up/'+cmds[1],data.paths[server_num]+'/', fileName[ len(fileName)-1] ,data.paths[server_num],n)
    # elif(p_cmd[0:5] =='downs'):
    #     cmds = cmd.split(' ')
    #     fileName = cmds[1].split('/')

    #     os.system( 'mkdir -p /Users/sam/ssh_data/'+server_info['name']+'/' )
    #     sftp.downs(scp_conns[ server_num ],data.paths[server_num] + '/' + cmds[1],'/Users/sam/ssh_data/'+server_info['name'])

    elif( p_cmd[0:4] == 'down' ):
        cmds = cmd.split(' ')
        if cmds[1][len(cmds[1])-1] == '/':
            cmds[1] = cmds[1][0:len(cmds[1])-1]
        fileName = cmds[1].split('/')
        os.system( 'mkdir -p "'+source_path+server_info['name']+'/"' )
        rs = check_down(
            server_num,
            data.paths[server_num] + '/' + cmds[1],
            source_path+server_info['name']+'/' ,
            fileName[ len(fileName)-1],data.paths[server_num] )
        if rs != 'n':
            if symtem_name == 'Darwin':
                os.system('open "'+source_path+server_info['name']+'/"')
            else:
                print('文件已下载到 "'+source_path+server_info['name']+'/"')
    elif(p_cmd == 'ls'):
        cmd = 'cd '+data.paths[server_num]+' && '+ cmd
        cmds[ n ] = ssh.cmd(server_num, cmd)
        print( cmds[ n ].replace('\n','   ') )
    else:
        cmd = 'cd '+data.paths[server_num]+' && '+ cmd
        cmds[ n ] = ssh.cmd(server_num, cmd)
        print( cmds[ n ] )

def check_confi_file():
    if os.path.isdir( os.path.expanduser('~')+'/.myssh' ):
        pass
    else:
        os.mkdir( os.path.expanduser('~')+'/.myssh' )
    if os.path.exists(yaml_path):
        pass
    else:
        f=open(yaml_path,'w')  
        f.write(config.yaml_demo_content)
        f.close()


def main():
    global ssh_complete,path_complete
    global relation
    global cmds
    global new_time

    check_confi_file()
    
    if len(sys.argv) > 1:
        for operate in sys.argv[1:]:
            if operate  == 'hideip':
                data.hideip = True

    if( len(sys.argv) >1 and sys.argv[1] == 'edit'):
        if symtem_name == 'Darwin':
            for editor in config.editors:
                if( os.path.exists(editor) ):
                    editor = editor.replace(' ','\ ')
                    os.system('open -a '+editor+' '+yaml_path)
                    return
            os.system('vim '+yaml_path)
        else:
            os.system('vim '+yaml_path)
        return
    # elif( len(sys.argv) >1 and sys.argv[1] == 'self'):
    #     if symtem_name == 'Darwin':
    #         os.system('open -a '+editor+' '+sys.path[0]+'/'+ ( sys.argv[0].split("/")[-1]) )
    #     else:
    #         os.system('vim '+sys.path[0]+'/'+ ( sys.argv[0].split("/")[-1]) )
    else:
        # f = open( sys.path[0]+'/'+yaml_path,'r')
        f = open( yaml_path,'r')
        result = list()
        relation ={}
        
        temp_result = yaml.load( f )
        group_code_list ={}
        f.close()
        if( temp_result == None ):
            show_str = '= =! 还没有服务器\nmyssh add      使用命令添加服务器信息'
        else:
            show_str = '服务器列表:\n'
            
            i = 0
            
            for v in temp_result:
                if( v.has_key('group') ):  #分组
                    if(v.has_key('code')):
                        show_str += '\33[42m\33[30m  %s [%s] \33[0m\n' % ( v['name'] ,v['code'] ) 
                        # group_code_list
                        group_code_list[v['code']]=list()
                    else:
                        show_str += '\33[42m\33[30m  %s  \33[0m\n' % ( v['name'] ) 
                    for l in v['group']:
                        l['password'] = str(l['password'])
                        result.append( l )


                        show_str += relation_add(l,i,'\33[42m \33[0m ')
                        if(v.has_key('code')):
                            group_code_list[v['code']].append(i)

                        i+=1
                    show_str +='\n'
                else:
                    v['password'] = str(v['password'])
                    result.append( v )
                    show_str += relation_add(v,i,'\33[40m \33[0m ')
                    i+=1

            data.servers = result
            if( len(sys.argv) >1 and  sys.argv[1] == "verify" ):
                n = 0
                verify_threads = []
                for server_info in result:
                    verify_threads.append( threading.Thread(target=threads_func.ssh_verify,args=('验证',n)) )
                    n += 1
                threads_func.threads_handle(verify_threads)
                
                exit()

            for x in relation:
                
                show_str = show_str.replace( '<<%s>>' %x, '    \33[41m ' + str( len( relation[x] ) ) + '台 \33[0m\33[45m %s \33[0m' %' | '.join(str(i) for i in relation[x])  )
            server = ''
            while(1):
                readline.set_completer(complete)

                global sever
                if(server == 'help'):
                    help_str='''
    \33[33mcmd\33[0m    服务器编号[...] 如 cmd 1 2 3 ,可操作多台服务器
    \33[33mcmd -l\33[0m 服务器编号  操作与服务器有关联的多台服务器 关联规则 服务器名-数字
    \33[33mcmd -g\33[0m 服务器编号  操作分组中的多台服务器,需要配置分组code
        \33[33mup\33[0m     上传文件 如 up 本地文件名 
        \33[33mdown\33[0m   下载文件 如 down 服务器文件名 本地文件名(可选)
        \33[33msync\33[0m   同步文件 "sync 服务器id > 被同步的服务器id(多个使用空格分隔)" 如 sync 1 > 2 3

        多台操作时 使用 "服务器id:操作指令" 可操作单台服务器 如 1:ls

    \33[33mexit\33[0m   返回上级操作
    \33[33mquit\33[0m   退出程序
                    '''
                    print( help_str )
                else:
                    print( show_str )
                try:
                    server = raw_input("输入服务器编号(help 帮助):")
                except KeyboardInterrupt:
                    print('')
                    server = 'quit'
                    pass
                if(server =='help'):
                    continue
                elif(server == 'quit' or server == 'exit' ):
                    exit()
                elif(server.find('cmd ') != -1):
                    

                    server_nums =  server.split(' ')
                    server_nums = list_del_empty( server_nums )
                    data.ssh_conns={}
                    data.scp_conns={}
                    data.paths={}

                    if( server.find('cmd -l') != -1 ):
                        server_list = relation[   regex.match( result[ int( server_nums[2] ) ]['name'] ).group(1)  ]
                        
                    elif( server.find('cmd -g') != -1 ):
                        server_list = group_code_list[ server_nums[2] ]
                    else:
                        server_list = server_nums[1:]
                        server_list = map(eval, server_list)

                    server_info = result[ int( server_list[0] ) ]
                    server_len =len( server_list )

                    connect_threads = []
                    for server_num in server_list:
                        connect_threads.append( threading.Thread(target=threads_func.threads_connect,args=('连接',server_num)) )
                    threads_func.threads_handle(connect_threads)
                    
                    for server_num in server_list: 
                        server_num = int(server_num)
                        server_info = result[ server_num ]

                        if( server_info.has_key('defaultPath') ):
                            temp_path = ssh.cd(server_num ,'cd ' + server_info['defaultPath'])
                            if( temp_path ):
                                data.paths[server_num] = temp_path
                            else:
                                data.paths[server_num] = ssh.cd(
                                    server_num,
                                    'cd ./' )
                        else:
                            data.paths[server_num] = ssh.cd(
                                server_num,
                                'cd ./' )

                        if( server_info.has_key('description') ):
                            print '\33[34m%d:\33[31m%s(%s) \33[0m' %(server_num,server_info['name'],common.hideip_fun(server_info['host']))
                            print( '\33[32m' + str(server_info['description']).replace('#',' \33[35m#').replace('\\n ','\33[32m\n') +'\33[0m\n' )

                    readline.set_completer(complete_path)
                    
                    data.heartbeat_paramiko_close.append( False )
                    
                    thread_ssh = threading.Thread(target=threads_func.heartbeat_ssh,args=(data.ssh_conns,len(data.heartbeat_paramiko_close)-1))
                    thread_ssh.setDaemon(True)
                    thread_ssh.start()


                    thread_scp = threading.Thread(target=threads_func.heartbeat_scp,args=(data.scp_conns,len(data.heartbeat_paramiko_close)-1))
                    thread_scp.setDaemon(True)
                    thread_scp.start()


                    
                    while(1):
                        cmds={}

                        i = 0
                        for server_num in server_list:
                            i+=1
                            server_num = int(server_num)
                            server_info = result[ server_num ]

                            if(server_len == i):
                                ssh_complete = server_num
                                path_complete = data.paths[ server_num ]
                                

                                try:
                                    print( '\33[34m%d:\33[33m%s@%s(%s):%s#\33[0m ' %(
                                        server_num,
                                        server_info['user'],
                                        server_info['name'],
                                        common.hideip_fun(server_info['host']),
                                        data.paths[server_num] ))

                                    p_cmd = raw_input('> ')

                                except KeyboardInterrupt:
                                    p_cmd ='exit'
                                    print('')
                            else:

                                print( '\33[34m%d:\33[33m%s@%s(%s):%s#\33[0m ' %(
                                    server_num,
                                    server_info['user'],
                                    server_info['name'],
                                    common.hideip_fun(server_info['host']),
                                    data.paths[server_num] ))


                        if( p_cmd == 'exit'):
                            data.heartbeat_paramiko_close[len(data.heartbeat_paramiko_close)-1] = True
                            for server_num in server_list:
                                server_num = int(server_num)
                                print '\33[31m正在断开连接：%s(%s) \33[0m' %(
                                    result[ server_num ]['name'],
                                    common.hideip_fun(result[ server_num ]['host']) )

                                data.ssh_conns[ server_num ].close()
                                data.scp_conns[ server_num ].close()
                            break
                        if(p_cmd == 'f5'):
                            reconnect_threads = []
                            for server_num in server_list:
                                reconnect_threads.append( threading.Thread(target=threads_func.threads_connect,args=('重连',server_num)) )
                            threads_func.threads_handle(reconnect_threads)
                            continue
                        if(p_cmd == 'detail'):
                            for server_num in server_list:
                                print ('\33[34m%d:\33[31m%s(%s)\33[0m' %(server_num,data.servers[server_num]['name'],common.hideip_fun(data.servers[server_num]['host']) ) )
                                
                                cmd ='''
    echo '\33[32m';\
    date -R;\
    echo 内网IP:$(ifconfig |head -n 2|grep "inet addr"|cut -b 21-80);\
    echo 系统:'\33[34m'$(head -n 1 /etc/issue) $(getconf LONG_BIT)位'\33[0m';\
    echo '\33[32m';\
    echo cpu:$(cat /proc/cpuinfo |grep "model name"| wc -l)核;\
    cat /proc/meminfo |grep 'MemTotal';\
    echo cpu使用情况:;\
    top -b -n 1 -1|grep Cpu;\
    echo 内存使用情况:;\
    free -m;\
    echo 负载:;\
    uptime;\
    echo 磁盘使用:;\
    df -hl;\
    echo '\33[0m'\
    '''
                                print ssh.cmd(server_num,cmd)
                            continue
                        if( p_cmd ==''):
                            continue

                        if( p_cmd == 'quit'):
                            exit()
                        n = 0
                        if( p_cmd[0:3] =='rm '):
                            certain = raw_input( '确定要执行删除命令吗?(y/n):' )
                            if( certain !='y'):
                                continue

                        if(p_cmd[0:5] =='sync '):
                            sync_info = p_cmd.split( '>' )
                            data.client_file={}
                            add_file ={}
                            temp_master  =  sync_info[0].split(' ')
                            temp_master = list_del_empty( temp_master )

                            master_server = int( temp_master[1] )
                            if  len(sync_info) > 1 :

                                client_server = sync_info[1].split(' ')
                                client_server = list_del_empty( client_server )

                            else:
                                client_server =list()
                                client_server.extend( server_list )
                                client_server.remove( master_server )

                            master_file = ssh.show_remote_file(
                                master_server,
                                data.paths[ master_server ])
                            master_remote_path = data.paths[master_server]
                            if not master_file:
                                print('  没有需要同步的文件')
                                continue
                            
                            scan_documents = []
                            for server_num in client_server:
                                server_num = int(server_num)
                                scan_documents.append( threading.Thread(target=threads_func.scan_document,args=('scan_document',server_num)) )
                            threads_func.threads_handle(scan_documents)

                            is_all_sync_file = False
                            for server_num in client_server:
                                server_num = int(server_num)
                                server_info = result[ server_num ]
                                print( '\33[34m%d:\33[31m%s(%s)\33[0m' %(
                                    server_num,server_info['name'],
                                    common.hideip_fun(server_info['host']) ))

                                add_file[ server_num ] =list()
                                is_sync_file= False
                                
                                for file_name in master_file:
                                    if( data.client_file[server_num].has_key(file_name)):
                                        if( master_file[ file_name ] > data.client_file[ server_num ][ file_name ]):

                                            x = time.localtime( master_file[ file_name ] )
                                            mtime = time.strftime('%Y-%m-%d %H:%M:%S',x)
                                            print( "  更新: %s 修改时间:%s" %( file_name, mtime) )
                                            add_file[ server_num ].append(file_name) 
                                            is_all_sync_file =True
                                            is_sync_file = True
                                    else:
                                        x = time.localtime( master_file[ file_name ] )
                                        mtime = time.strftime('%Y-%m-%d %H:%M:%S',x)

                                        print( "  添加: %s 修改时间:%s"%( file_name,  mtime) )
                                        add_file[ server_num ].append(file_name) 
                                        is_all_sync_file =True
                                        is_sync_file = True
                                if( not is_sync_file ):
                                    print('  没有需要同步的文件')

                            if( not is_all_sync_file ):
                                continue
                            certain = raw_input('确定要同步吗?(y/n):')
                            if( certain !='y'):
                                continue
                            else:
                                files_list =list()
                                for server_num in add_file:

                                    client_remote_path = data.paths[server_num]

                                    server_info = result[ master_server ]
                                    files_list.extend(add_file[ server_num ])

                                files_list = list( set(files_list) )
                                print( '\33[34m%d:\33[31m%s@%s(%s)\33[0m 下载中' %(
                                    master_server,server_info['user'],
                                    server_info['name'],
                                    common.hideip_fun(server_info['host']) ))

                                for file_name in files_list:
                                    os.system('mkdir -p "'+ source_path+result[master_server]['name']+'-SYNC/' +file_name[0:file_name.rindex('/')] + '/"')
                                    
                                    print(' ' + file_name[file_name.index('/')+1:])
                                    sftp.down(
                                        master_server,
                                        master_remote_path +'/'+file_name[file_name.index('/')+1:],
                                        source_path+result[master_server]['name']+'-SYNC/'+file_name )

                                for server_num in add_file:
                                    server_info = result[ server_num ]
                                    print( '\33[34m%d:\33[31m%s@%s(%s)\33[0m 上传中' %(
                                        server_num,server_info['user'],
                                        server_info['name'],
                                        common.hideip_fun(server_info['host']) ))

                                    for file_name in add_file[server_num]:
                                        if(file_name.count('/') > 1):
                                            try:
                                                cmd = 'mkdir -p "' + client_remote_path + file_name[ file_name.index('/'):file_name.rindex('/')] + '/"'
                                                ssh.cmd(server_num, cmd)

                                            except Exception,e:
                                                pass
                                        print(' ' + file_name[file_name.index('/')+1:])
                                        sftp.upload(
                                            server_num,
                                            source_path+result[master_server]['name']+'-SYNC/'+file_name,
                                            client_remote_path +'/'+file_name[file_name.index('/')+1:] )


                            continue

                        if(p_cmd[0:7] =='script '):
                            certain = raw_input( '确定要执行脚本命令吗?(y/n):' )
                            if( certain !='y'):
                                continue
                            else:
                                p_cmd = p_cmd.split(' ')
                                scripts = open( source_path+'script/'+p_cmd[1] ,"r")
                                script_err =''
                                for script in scripts.readlines():
                                    p_cmd = script.strip('\n')
                                    if( p_cmd[0:1] =='#' ):
                                        continue
                                    cmds={}
                                    i = 0
                                    n = 0
                                    server_num_arr = regex_cmd.match(p_cmd)


                                    if(server_num_arr):
                                        if( not data.paths.has_key( int( server_num_arr.group(1) ) ) ):
                                            script_err ='notpath'
                                            print('您不能操作未连接的服务器')
                                            break
                                        print( '\33[34m%d:\33[33m%s@%s(%s):%s#\33[0m%s' %(
                                            int( server_num_arr.group(1) ),
                                            server_info['user'],
                                            server_info['name'],
                                            common.hideip_fun(server_info['host']),
                                            data.paths[ int( server_num_arr.group(1) ) ],
                                            p_cmd ))
                                    else:
                                        for server_num in server_list:
                                            i+=1
                                            server_num = int(server_num)
                                            server_info = result[ server_num ]

                                            if(server_len == i):
                                                ssh_complete = server_num
                                                path_complete = data.paths[ server_num ]
                                                print( '\33[34m%d:\33[33m%s@%s(%s):%s#\33[0m%s' 
                                                    %( server_num,server_info['user'],
                                                        server_info['name'],
                                                        common.hideip_fun(server_info['host']),
                                                        data.paths[server_num],
                                                        p_cmd )  )
                                            else:
                                                print( '\33[34m%d:\33[33m%s@%s(%s):%s#\33[0m' 
                                                    %( server_num,server_info['user'],
                                                        server_info['name'],
                                                        common.hideip_fun(server_info['host']),
                                                        data.paths[server_num] )  )
                                    
                                    if( 'notpath' == script_err ):
                                        break


                                    new_time = time.time()
                                    if( server_num_arr ):
                                
                                        script_err = ssh_cmd_func( 
                                            int(server_num_arr.group(1)),
                                            result,server_num_arr.group(2),
                                            data.ssh_conns,
                                            source_path,
                                            n) 
                                        if( 'notpath' == script_err):
                                            print('\33[31m脚本停止执行!!\33[31m')
                                            break
                                    else:
                                        for server_num in server_list:
                                            ssh_cmd_func(
                                                server_num,
                                                result,
                                                p_cmd,
                                                data.ssh_conns,
                                                source_path,
                                                n ) 

                                            if( 'notpath' == script_err ):
                                                print('\33[31m脚本停止执行!!\33[31m')
                                                break
                                            n+=1
                                        if( 'notpath' == script_err ):
                                            break

                                    if( 'notpath' == script_err ):
                                        break
                                    if( p_cmd[0:2] != 'cd' and p_cmd[0:2] != 'up' and p_cmd[0:4] != 'down' ):
                                        for x in range(n-1):
                                            if( cmds[x] != cmds[x+1] ):
                                                print( '\33[34m执行结果不一致\33[0m' )
                                                break


                                continue


                        new_time = time.time()

                        server_num_arr = regex_cmd.match(p_cmd) 
                        if( server_num_arr ):
                            server_num = server_num_arr.group(1)
                            if( not data.paths.has_key( int( server_num ) ) ):
                                print('您不能操作未连接的服务器')
                                continue
                            p_cmd = server_num_arr.group(2)
                            if( p_cmd[0:3] =='rm '):
                                certain = raw_input( '确定要执行删除命令吗?(y/n):' )
                                if( certain !='y'):
                                    continue
                            ssh_cmd_func(
                                server_num,
                                result,
                                p_cmd,
                                data.ssh_conns,
                                source_path,
                                n )
                        else:
                            for server_num in server_list:
                                ssh_cmd_func(
                                    server_num,
                                    result,
                                    p_cmd,
                                    data.ssh_conns,
                                    source_path,
                                    n )
                                n+=1    

                        if( p_cmd[0:2] != 'cd' and p_cmd[0:2] != 'up' and p_cmd[0:4] != 'down' ):
                            for x in range(n-1):
                                if( cmds[x] != cmds[x+1] ):
                                    print( '\33[34m执行结果不一致\33[0m' )
                                    break


                else:
                    login_cmd = ''
                    if( not is_number( server ) ):
                        server_arr = ssh_login_cmd.match(server)
                        if( not server_arr ):
                            continue
                        server_num = int( server_arr.group(1) )
                        login_cmd = server_arr.group(2)+';'
                    else:
                        server_num = int(server)

                    server_info = result[ server_num ]

                    print u'\n\33[31m正在连接：%s(%s) \33[0m' %( server_info['name'],common.hideip_fun(server_info['host']) ) 
                    
                    if( server_info.has_key('description') ):
                        print( '\33[32m' + server_info['description'].replace('#',' \33[35m#').replace('\\n ','\33[32m\n') +'\33[0m\n' )
                    if(server_info.has_key('port')):
                        port = server_info['port']
                    else:
                        port = '22'
                    threads_func.ssh_verify('验证',server_num)
                    if( server_info.has_key('defaultPath') ):

                        os.system('''%s -p '%s' ssh %s@%s -p %s -t '\
                            echo "\033[33m ";\
                            date -R;echo '';\
                            echo 内网IP:$(ifconfig |head -n 2|grep "inet addr"|cut -b 21-80);\
                            echo 系统:$(head -n 1 /etc/issue) $(getconf LONG_BIT)位;\
                            echo cpu:$(cat /proc/cpuinfo |grep "model name"| wc -l)核;\
                            cat /proc/meminfo |grep 'MemTotal';echo 磁盘使用:;\
                            df -hl;\
                            echo "\033[0m";\
                            ' ''' %( sshpass, server_info['password'], server_info['user'], server_info['host'] ,port) )
                        
                        os.system("%s -p '%s' ssh %s@%s -p %s -o ServerAliveInterval=60 -t  'cd %s;%sbash;'" %( sshpass, server_info['password'], server_info['user'], server_info['host'] ,port,server_info['defaultPath'] ,login_cmd) )

                    else:

                        os.system("%s -p '%s' ssh %s@%s  -o ServerAliveInterval=60 -p %s" %( sshpass, server_info['password'], server_info['user'], server_info['host'] ,port) )

if __name__ == '__main__':
    main()