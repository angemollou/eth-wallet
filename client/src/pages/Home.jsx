import React, { useEffect, useContext, useState } from 'react'
import useAuth from '../hooks/useAuth'
import useUserList from '../hooks/useUserList';
import { AuthContext } from '../context/AuthContext';

export default function Home() {
    const { user } = useAuth();
    const { userList } = useContext(AuthContext);
    const getUsers = useUserList()
    const [page, setPage] = useState(1);


    useEffect(() => {
        getUsers(page)
    }, [user, page])

    return (
        <div className='container mt-3'>
            <div className="mb-12">
                <h2>
                    {user?.email !== undefined ? 'List user Ethereum balance' : 'Please login first'}
                </h2>
            </div>
            {user && <div className='row'>
                <table className="table table-sm">
                    <thead>
                        <tr>
                            <th scope="col">#</th>
                            <th scope="col">Email</th>
                            <th scope="col">Balance</th>
                        </tr>
                    </thead>
                    <tbody>
                        {userList.page && userList.page.map((item, i) =>
                            <tr key={i}>
                                <th scope="row">{i + 1}</th>
                                <td>{item?.email}</td>
                                <td>{item?.balance_eth} ETH</td>
                            </tr>
                        )}
                    </tbody>
                </table>
                {userList.pagination && userList.pagination.count
                    && <nav aria-label="Page navigation">
                        <ul className="pagination justify-content-center">
                            {(page - 1) === 1
                                && <>
                                    <li className="page-item">
                                        <button className="page-link text-dark"
                                            onClick={() => setPage(page - 1)} aria-label="Previous">
                                            <span aria-hidden="true">&laquo;</span>
                                        </button>
                                    </li>
                                    <li className="page-item">
                                        <button className="page-link text-dark"
                                            onClick={() => setPage(page - 1)}>{page - 1}</button>
                                    </li>
                                </>
                            }
                            <li className="page-item">
                                <button className="page-link text-light active">{page}</button>
                            </li>
                            {(page + 1) < userList.pagination.count
                                && <>
                                    <li className="page-item">
                                        <button className="page-link text-dark"
                                            onClick={() => setPage(page + 1)}>{page + 1}</button>
                                    </li>
                                    <li className="page-item">
                                        <button className="page-link text-dark"
                                            onClick={() => setPage(page + 1)} aria-label="Next">
                                            <span aria-hidden="true">&raquo;</span>
                                        </button>
                                    </li>
                                </>
                            }
                        </ul>
                    </nav>
                }
            </div>}
        </div>
    )
}
